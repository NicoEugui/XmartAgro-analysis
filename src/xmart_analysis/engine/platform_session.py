"""A platform session: validate the answers, read the sensor, run the engine and assemble the outputs.

This is the logic the backend would run. It takes the same answers the platform collects (sensor, producer,
agronomist data, options to compare), checks them (all errors are returned together, each tied to a field),
and returns a language-neutral document with the three outputs: the main screen, the option cards and the
data sheet. Rendering (figures, terminal text) is done elsewhere, from this document only.
"""

import json
import re
from datetime import date, datetime

from . import crops_uy as cu
from . import platform_contract as pc
from . import rotations
from . import context as _context
from . import sensor_input as si
from . import sensor_sources as ss
from . import sowing_scenarios as sw
from . import water_model as wm
from . import water_scenarios as ws
from . import tables
from .errors import EngineError
from .i18n import label, resolve

CROP_CHOICES = ["soybean_1st", "soybean_2nd", "maize", "maize_2nd", "sorghum_1st", "sorghum_2nd", "wheat", "barley",
                "rapeseed"]
# Past seasons also admit crops the model cannot simulate yet and non-crop covers: valid history, never sent to the engine.
HISTORY_CROP_CHOICES = CROP_CHOICES + ["oat_cover", "lotus", "red_clover", "pasture_mix", "sunflower", "carinata", "vetch",
                                       "alfalfa", "fallow"]
SEASON_CHOICES = [f"{y}/{(y + 1) % 100:02d}" for y in range(tables.constant("history_last_season_year"),
                                                          tables.constant("history_first_season_year") - 1, -1)]
MAX_OPTIONS = tables.constant("max_options")
SEASON_RE = re.compile(r"^(19|20)\d{2}/\d{2}$")
LIMITS = {key: (tables.constant(f"{key}_min"), tables.constant(f"{key}_max"))
          for key in ("organic_matter_pct", "phosphorus_ppm", "ph", "erosion_t_ha_yr", "yield_kg_ha")}

def crop_label_key(crop_id):
    return cu.name_label_key(crop_id) if crop_id in cu.CROPS else f"crops_known.{crop_id}"


def _closed_choice(value, allowed, field):
    """A value must be one of the offered options (a dropdown), never free text."""
    if value not in allowed:
        raise EngineError("invalid_choice", field, f"{field} must be one of the offered options, got {value!r}",
                          received=repr(value), allowed=list(allowed))
    return value


def parse_month_day(value, field):
    """'MM-DD' (or a [month, day] pair) to a (month, day) tuple; raises a structured error otherwise."""
    if isinstance(value, str):
        m = re.fullmatch(r"\s*(\d{1,2})-(\d{1,2})\s*", value)
        value = (int(m.group(1)), int(m.group(2))) if m else None
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        value = tuple(value)
    else:
        value = None
    return ws.validate_month_day(value, field)


def _collect(errors, field, fn):
    try:
        return fn()
    except EngineError as exc:
        d = exc.to_dict()
        d["field"] = field
        errors.append(d)
    return None


def _number(value, field, key):
    if value is None:
        return None
    lo, hi = LIMITS[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value or not lo <= value <= hi:
        raise EngineError("value_out_of_range", field, f"{field} must be a number between {lo} and {hi}", received=repr(value),
                          minimum=lo, maximum=hi)
    return float(value)


def validate_answers(answers):
    """All problems of a set of answers (empty list if valid); each one is a structured error tied to a field."""
    errors = []
    if not isinstance(answers, dict):
        return [{"code": "invalid_answers", "field": "answers", "message": "Answers must be an object", "details": {}}]
    sensor = answers.get("sensor") or {}
    kind = sensor.get("source", "simulated")
    if kind not in ("simulated", "manual"):
        _collect(errors, "sensor.source", lambda: ss.source_from_answers(sensor))
    if kind == "manual":
        _collect(errors, "sensor.moisture", lambda: si.validate_theta(sensor.get("moisture")))
    _collect(errors, "reading_date", lambda: parse_month_day(answers.get("reading_date"), "reading_date"))
    current = answers.get("current_crop")
    if current:
        _collect(errors, "current_crop.crop", lambda: _check_sowable(current.get("crop")))
        _collect(errors, "current_crop.sowing", lambda: parse_month_day(current.get("sowing"), "current_crop.sowing"))
    seasons_given = [x.get("season") for x in answers.get("past_seasons") or []]
    if len(set(seasons_given)) != len(seasons_given):
        errors.append({"code": "duplicate_season", "field": "past_seasons", "message": "Each season can be entered once",
                       "details": {"seasons": seasons_given}})
    for i, s in enumerate(answers.get("past_seasons") or []):
        base = f"past_seasons[{i}]"
        _collect(errors, f"{base}.season", lambda s=s: _closed_choice(s.get("season"), SEASON_CHOICES, f"{base}.season"))
        crops = s.get("crops", [])
        if not isinstance(crops, list):
            errors.append({"code": "invalid_choice", "field": f"{base}.crops",
                           "message": f"{base}.crops must be a list of offered crops, not text", "details": {"allowed": HISTORY_CROP_CHOICES}})
        else:
            for c in crops:
                _collect(errors, f"{base}.crops", lambda c=c: _closed_choice(c, HISTORY_CROP_CHOICES, f"{base}.crops"))
        rating = s.get("rating")
        if rating is not None and (isinstance(rating, bool) or rating not in (1, 2, 3, 4, 5)):
            errors.append({"code": "value_out_of_range", "field": f"{base}.rating",
                           "message": "Rating must be 1 to 5", "details": {"received": repr(rating)}})
        _collect(errors, f"{base}.yield_kg_ha", lambda s=s: _number(s.get("yield_kg_ha"), f"{base}.yield_kg_ha", "yield_kg_ha"))
    for key in ("organic_matter_pct", "phosphorus_ppm", "ph", "erosion_t_ha_yr"):
        _collect(errors, f"agronomist.{key}", lambda key=key: _number((answers.get("agronomist") or {}).get(key),
                                                                       f"agronomist.{key}", key))
    adate = (answers.get("agronomist") or {}).get("analysis_date")
    if adate and not re.fullmatch(r"(19|20)\d{2}-(0[1-9]|1[0-2])", str(adate)):
        errors.append({"code": "invalid_date", "field": "agronomist.analysis_date",
                       "message": "Analysis date must look like 2026-05", "details": {"received": repr(adate)}})
    options = answers.get("options")
    if not isinstance(options, list) or not options:
        errors.append({"code": "required_field", "field": "options", "message": "Pick at least one option to compare",
                       "details": {}})
    elif len(options) > MAX_OPTIONS:
        errors.append({"code": "too_many_options", "field": "options",
                       "message": f"At most {MAX_OPTIONS} options can be compared", "details": {"received": len(options)}})
    else:
        for i, o in enumerate(options):
            base = f"options[{i}]"
            if o.get("kind") == "crop":
                _collect(errors, f"{base}.crop", lambda o=o: _check_sowable(o.get("crop")))
                _collect(errors, f"{base}.sowing", lambda o=o: parse_month_day(o.get("sowing"), f"{base}.sowing"))
            elif o.get("kind") == "rotation":
                if o.get("rotation") not in rotations.ids():
                    errors.append({"code": "unknown_rotation", "field": f"{base}.rotation",
                                   "message": f"Unknown rotation {o.get('rotation')!r}", "details": {"known": rotations.ids()}})
            else:
                errors.append({"code": "unknown_option_kind", "field": f"{base}.kind",
                               "message": "Option kind must be 'crop' or 'rotation'", "details": {"received": repr(o.get("kind"))}})
    return errors


def _check_sowable(crop):
    spec = cu.require_crop(crop)
    if spec.get("perennial") or crop == "oat_cover":
        raise EngineError("crop_cannot_be_sown_on_a_date", "crop", f"'{crop}' has no sowing date in this flow", crop=crop)
    return crop


def _md(value):
    return f"{value[0]:02d}-{value[1]:02d}"


def _season_classes(doc):
    return [{"season": r["season"], "class": r["class"]} for r in doc["season_results"]]


def _crop_card(crop, sowing, theta, reading_md, is_current, kw, info):
    doc = sw.evaluate_sowing(crop, sowing, theta, reading_md, source_info=info, **kw)
    ref = ws.safe_date(2001, *sowing)
    start, end = cu.critical_window_from_sowing(crop, ref)
    return {"kind": "crop", "id": f"{crop}@{_md(sowing)}", "is_current": is_current, "title": doc["crop"]["name"],
            "sowing": _md(sowing), "scenarios": doc["scenarios"], "high_deficit_seasons": doc["season_counts"]["high_deficit"],
            "season_counts": doc["season_counts"], "split_in_10_parts": doc["split_in_10_parts"],
            "critical_window": {"start": f"{start.day:02d}/{start.month:02d}", "end": f"{end.day:02d}/{end.month:02d}"},
            "median_water_at_sowing_mm": doc["median_water_at_sowing_mm"],
            "season_classes": _season_classes(doc),
            "warnings": [{"code": w["code"], "label": w["label"]} for w in doc["warnings"]],
            "soil": {"state": "no_field_diagnosis"}, "confidence": "low", "metadata": doc["metadata"]}


def _current_crop_card(crop, sowing, theta, reading_md, kw, info):
    doc = sw.evaluate_current_crop(crop, sowing, theta, reading_md, source_info=info, **kw)
    card = {"kind": "crop", "id": f"{crop}@{_md(sowing)}", "is_current": True, "title": doc["crop"]["name"],
            "sowing": _md(sowing), "status": doc["status"], "day_of_cycle": doc["day_of_cycle"],
            "cycle_days": doc["crop"]["cycle_days"], "scenarios": doc["scenarios"],
            "warnings": [{"code": w["code"], "label": w["label"]} for w in doc["warnings"]],
            "soil": {"state": "no_field_diagnosis"}, "confidence": "low", "metadata": doc["metadata"],
            "high_deficit_seasons": None, "season_counts": None, "split_in_10_parts": None, "critical_window": None}
    if doc["scenarios"]:
        ref, _ = sw.last_sowing_on_or_before(sowing, reading_md, 2001)
        start, end = cu.critical_window_from_sowing(crop, ref)
        card.update({"high_deficit_seasons": doc["season_counts"]["high_deficit"], "season_counts": doc["season_counts"],
                     "split_in_10_parts": doc["split_in_10_parts"],
                     "critical_window": {"start": f"{start.day:02d}/{start.month:02d}", "end": f"{end.day:02d}/{end.month:02d}"},
                     "season_classes": _season_classes(doc),
                     "critical_stage_remaining_fraction": doc["critical_stage_remaining_fraction"]})
    return card


def _rotation_card(rotation_id, kw):
    r = rotations.evaluate(rotation_id, kw)
    crops = [{"survey_crop": e["survey_crop"], "engine_crop": e["engine_crop"], "status": e["status"],
              "name": label(crop_label_key(e["engine_crop"] or e["survey_crop"]))} for e in r["entries"]]
    return {"kind": "rotation", "id": rotation_id, "is_current": False, "title": label("rotation.title", n=r["respondent"]),
            "crops": crops, "crops_modelled": r["crops_modelled"], "combinations": r["combinations"],
            "high_deficit_combinations": r["season_counts"]["high_deficit"], "season_counts": r["season_counts"],
            "split_in_10_parts": r["split_in_10_parts"], "season_classes": r["season_classes"], "note": label("rotation.note"),
            "warnings": [], "soil": {"state": "no_field_diagnosis"}, "confidence": "low", "metadata": rotations.METADATA}


def _lookup(inputs, path):
    node = inputs
    for part in path.split("."):
        if isinstance(node, list):
            return [x.get(part) if isinstance(x, dict) else None for x in node]
        node = node.get(part) if isinstance(node, dict) else None
    return node


def build_session(answers, sensor_info=None, context=None):
    """Validate, read the sensor, run the engine; returns the language-neutral session document."""
    errors = validate_answers(answers)
    if errors:
        raise EngineError("invalid_answers", "answers", f"{len(errors)} answer(s) are invalid", errors=errors)
    info = sensor_info or ss.source_from_answers(answers.get("sensor")).read()
    theta = info["volumetric_moisture"]
    if info.get("timestamp"):  # a real reading dictates its own date
        stamp = datetime.fromisoformat(info["timestamp"])
        reading_md = (stamp.month, stamp.day)
    else:
        reading_md = parse_month_day(answers["reading_date"], "reading_date")
    context = context or _context.build_context()
    kw = {"params": context["params"], "weather": context["weather"], "et0": context["et0"]}
    scenarios = ws.build_scenarios(theta, start=reading_md, source_info=info, **kw)
    scenarios["initial_state"]["sensor"]["reading_day"] = _md(reading_md)  # the day the reading is for, also when no timestamp

    cards, seen = [], set()
    current = answers.get("current_crop")
    if current:
        md = parse_month_day(current["sowing"], "current_crop.sowing")
        cards.append(_current_crop_card(current["crop"], md, theta, reading_md, kw, info))
        seen.add((current["crop"], md))
    for o in answers["options"]:
        if o["kind"] == "rotation":
            cards.append(_rotation_card(o["rotation"], kw))
            continue
        md = parse_month_day(o["sowing"], "sowing")
        if (o["crop"], md) in seen:
            continue
        seen.add((o["crop"], md))
        cards.append(_crop_card(o["crop"], md, theta, reading_md, False, kw, info))

    inputs = {"location": {"latitude": tables.constant("latitude"), "longitude": tables.constant("longitude"),
                           "source": "nasa_power", "note": label("location.note")},
              "sensor": {"source": info["source"], "moisture": theta, "sensor_id": info.get("sensor_id"),
                         "timestamp": info.get("timestamp"), "depth_cm": info.get("depth_cm")},
              "reading_date": _md(reading_md), "current_crop": current, "past_seasons": answers.get("past_seasons") or [],
              "agronomist": answers.get("agronomist") or {}, "options": answers["options"]}
    rows = []
    for f in pc.INPUT_FIELDS:
        path = f["field"].replace("sensor.moisture", "sensor.moisture")
        value = _lookup(inputs, path)
        entered = value not in (None, [], {}) and not (isinstance(value, list) and all(v is None for v in value))
        rows.append({"field": f["field"], "label": label(f["label"]), "source": f["source"], "value": value,
                     "entered": entered, "status": f["status"], "outputs": f["outputs"]})
    seasons = [int(s["season"][:4]) for s in inputs["past_seasons"]] or list(range(2025, 2020, -1))
    rain = [{"season": ws.season_name(y), "rain_dec_mar_mm": round(wm.rain_between(context["weather"], date(y, 12, 1),
                                                                                   date(y + 1, 4, 1)), 1)}
            for y in sorted(set(seasons)) if date(y + 1, 3, 31) <= max(context["weather"]) and date(y, 12, 1) >= min(context["weather"])]
    return {
        "schema_version": "1.0",
        "inputs": inputs,
        "contract": [{"field": f["field"], "label": label(f["label"]), "source": f["source"], "status": f["status"],
                      "outputs": f["outputs"], "required": f["required"]} for f in pc.INPUT_FIELDS],
        "outputs": {"main_screen": {"soil_water": scenarios["initial_state"]["sensor"], "scenarios": scenarios},
                    "option_cards": cards},
        "data_sheet": {"rows": rows, "rain_dec_mar_context": {"source": "NASA POWER", "used_by_engine": False, "seasons": rain}},
    }


def engine_fingerprint(session):
    """Everything the engine produced (not the echo of the inputs), as a comparable string."""
    return json.dumps(resolve(session["outputs"], "en"), sort_keys=True)
