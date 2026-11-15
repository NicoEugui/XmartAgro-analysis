"""The `learning` block of the frontend document: what the three models (A, B, C) add to the analysis, read from the registry.

It is built only from published models and only when a registry folder is given, so a checkout without one still exports the same analysis (the block is null).
Everything here comes from a model trained on the simulated panel, and says so (`simulated`). A, B and C are applied the way the nightly pipeline would apply
them: A classifies the seasons of each option (instead of the fixed cuts), B corrects the satellite of the demo field, C proposes the crop history from the
real MODIS curve of the demo field's point.
"""

from pathlib import Path

from ..engine import crops_uy as cu
from ..engine import tables
from ..engine import water_scenarios as ws
from ..engine.i18n import label
from ..learning import examples, ndvi
from ..learning.apply import Adjustments, field_id
from ..learning.registry import Registry
from ..learning.stores import SeriesStore
from ..validation import ndvi as ndvi_validation

RECENT_DAYS = 90  # days of the satellite series shown
MIN_COMPOSITES = 20  # good MODIS composites a season needs to be read by model C


def _models(published):
    out = []
    for name, (entry, learner) in published.items():
        scores = {k: v["mean"] for k, v in entry["validation"]["metrics"].items()}
        primary, baseline = scores[learner.primary], scores[learner.baseline]
        out.append({"id": name, "role": label(f"learn.model.{name}.role"), "version": entry["version"], "state": entry["state"], "trained_on": entry["trained_on"],
                    "examples": entry["n_examples"], "fields": entry["n_fields"], "simulated_data": entry["simulated_data"],
                    "metric": {"name": label(f"learn.metric.{learner.primary}"), "value": round(primary, 4), "fixed_rule": round(baseline, 4),
                               "fixed_rule_name": label(f"learn.metric.{learner.baseline}"), "lower_is_better": learner.lower_is_better, "better": learner.improves(scores)},
                    "reason": entry["reason"]})
    return out


def _options(adjustments, cards):
    """Model A on every option, next to the fixed cuts: of 10 crop-seasons, how many it expects the producer to call bad, normal or good.

    These are the same numbers the option cards carry as their drops when the models are applied (`summary.options[].risk_basis`)."""
    out = []
    for card in cards:
        risk = adjustments.risk(card)
        if risk:
            out.append({"id": card["id"], "model_version": risk["model_version"], "seasons": risk["seasons"], "of_10": risk["drops"],
                        "water_risk": risk["water_risk"], "fixed_cuts_of_10": risk["fixed_cuts_drops"],
                        "fixed_cuts_water_risk": risk["fixed_cuts_water_risk"]})
    return out


def _satellite(model_b, entry, folder):
    """Model B on the demo field's last days: the satellite as it is and corrected, next to the (simulated) sensor."""
    field = field_id()
    store = SeriesStore(Path(folder) / "series")
    rows = examples.sensor_examples(store.rows("daily", field), store.rows("nodes", field))
    rows = sorted(rows, key=lambda r: r["date"])[-RECENT_DAYS:]
    if not rows:
        return None
    corrected = [round(float(v), 4) for v in model_b.predict(rows)]
    raw = [r["smap"] for r in rows]
    sensor = [r["sensor"] for r in rows]

    def rmse(values):
        return round((sum((v - s) ** 2 for v, s in zip(values, sensor)) / len(sensor)) ** 0.5, 4)
    return {"model_version": entry["version"], "field_id": field, "dates": [r["date"] for r in rows], "satellite": raw, "corrected": corrected, "sensor": sensor,
            "rmse": {"satellite": rmse(raw), "corrected": rmse(corrected)}, "unit": "m3/m3", "sensor_simulated": True,
            "in_sample": True, "note": label("learn.satellite.note")}


def _crop_history(model_c, entry):
    """Model C on the real MODIS curve of the demo field's point, one season at a time. With enough confidence it is a proposal for the producer to
    confirm; with little it is a question (`ask`). The model learned from simulated curves, so on a real mixed pixel it is often unsure."""
    composites = ndvi_validation.load(tables.site_file("modis_ndvi.csv"))
    seasons = []
    for year in range(composites[0][0].year, composites[-1][0].year):
        series = ndvi.from_composites(composites, year)
        if len(series) >= MIN_COMPOSITES:
            seasons.append((year, ndvi.summary(series)))
    proposals = model_c.propose([s for _, s in seasons])
    return [{"season": ws.season_name(year), "crop": crop, "crop_name": label(cu.name_label_key(crop)) if crop in cu.CROPS else label("learn.fallow"),
             "confidence": round(confidence, 2), "action": "propose" if confidence >= tables.constant("learn_propose_min_confidence") else "ask", "confirmed": False, **{k: summary[k] for k in ndvi.FEATURES}}
            for (year, summary), (crop, confidence) in zip(seasons, proposals)]


def build(folder, cards, adjustments=None):
    """The block, or None when `folder` is None or holds no published A, B and C. `adjustments` (the published A and B applied to the field) are loaded when not given."""
    if folder is None:
        return None
    registry = Registry(folder)
    published = {name: registry.published(name) for name in ("B", "A", "C")}
    if not all(published.values()):
        return None
    (entry_b, model_b), (entry_a, model_a), (entry_c, model_c) = published["B"], published["A"], published["C"]
    return {"simulated": all(e["simulated_data"] for e, _ in published.values()), "note": label("learn.note"), "models": _models(published),
            "options": _options(adjustments or Adjustments(folder, entry_a, model_a, entry_b, model_b), cards), "satellite": _satellite(model_b, entry_b, folder), "crop_history": _crop_history(model_c, entry_c)}
