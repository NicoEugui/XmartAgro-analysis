"""Rotations the surveyed producers reported, evaluated at the NASA POWER point.

A rotation is the list of crops a producer wrote, in the written order (the producers do not say which crop falls in which
year). Each modelled crop is run over every historical season at its default sowing date with the same starting moisture, so
only the climate differs, and the counts of the crops are added. Years are independent: this is neither a simulation of
the sequence, a forecast nor a ranking. For a chart with one result per season, a season of a rotation is classed by the mean
unmet demand of its modelled crops that season.
"""

from . import crops_uy as cu
from . import deficit, tables
from . import sowing_scenarios as sw

METADATA = {"type": "exploratory_simulation", "validation": "not_validated_for_rotations", "robust_comparison": False,
            "parameter_source": "NASA climate; crop parameters pending a dataset", "applicable_to_field": False}


def survey_crop_to_engine(survey_crop, previous):
    """The modelled crop for a written crop, given the crop written right before it in the same group (or None)."""
    mapping = tables.survey_crop_map()
    return mapping.get((survey_crop, previous or ""), mapping.get((survey_crop, "")))


def entries(respondent):
    """Each written crop with the crop it is modelled as and whether the model reports its stress."""
    out, previous, group = [], None, None
    for g, survey_crop, _ in tables.survey_rotations()[respondent]:
        previous = previous if g == group else None
        engine_crop = survey_crop_to_engine(survey_crop, previous)
        risk = bool(engine_crop and cu.CROPS[engine_crop]["counts_risk"])
        out.append({"survey_crop": survey_crop, "engine_crop": engine_crop,
                    "status": "modelled" if risk else "cover_without_risk" if engine_crop else "not_modelled"})
        previous, group = survey_crop, g
    return out


def ids():
    """Rotations with at least one crop whose stress the model reports."""
    return [f"survey_{r:02d}" for r in sorted(tables.survey_rotations()) if any(e["status"] == "modelled" for e in entries(r))]


def respondent_of(rotation_id):
    return int(rotation_id.split("_")[1])


def evaluate(rotation_id, kw):
    """Counts of the season classes over all modelled crop-years; `kw` holds params, weather and et0."""
    respondent = respondent_of(rotation_id)
    theta = tables.constant("rotation_start_theta")
    totals, n, listed, stress = {c: 0 for c in deficit.CLASSES}, 0, [], {}
    for entry in entries(respondent):
        entry = dict(entry)
        if entry["status"] == "modelled":
            sowing = cu.CROPS[entry["engine_crop"]]["sowing"]
            doc = sw.evaluate_sowing(entry["engine_crop"], sowing, theta, sowing, **kw)
            entry["season_counts"], entry["scenarios"] = doc["season_counts"], doc["scenarios"]
            n += doc["scenarios"]
            for row in doc["season_results"]:
                stress.setdefault(row["season"], []).append(row["stress"])
            for c in deficit.CLASSES:
                totals[c] += doc["season_counts"][c]
        listed.append(entry)
    return {"id": rotation_id, "respondent": respondent, "entries": listed, "combinations": n, "season_counts": totals,
            "split_in_10_parts": deficit.split_in_10(totals, n),
            "season_classes": [{"season": season, "class": deficit.classify(sum(v) / len(v))} for season, v in sorted(stress.items())],
            "crops_modelled": sum(e["status"] == "modelled" for e in listed)}
