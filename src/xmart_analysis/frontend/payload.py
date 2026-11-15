"""The static data the frontend renders, in the shape of the panel's API contract (`summary`, `inputs`, `scenarios`).

The model's own results, normalised to what the screens show: the main screen (water, soil, option cards), the data-entry screen
(producer and agronomist) and the scenario chart. Built only from the language-neutral session and the data tables, so a value on
screen is something the engine returned, something a person entered or a label. Where the model has nothing to say (soil state,
soil effect...) the field is null. Text fields are `{key, en, es}` label objects. The contract is `schema.py`.
"""

import json
from collections import Counter

from ..engine import deficit, tables
from ..engine import platform_session as ps
from ..engine import water_scenarios as ws
from ..engine.i18n import label

SCHEMA_VERSION = "2.1"
MODES = ("demo", "live", "error", "offline")  # the states the panel can be in; the last one is decided by the panel itself


def _field():
    site_id = tables.active_site()
    row = tables.sites()[site_id]
    return {"id": site_id, "name": row["name"], "department": row["department"], "lat": tables.constant("latitude"),
            "lon": tables.constant("longitude")}


def _site():
    site_id = tables.active_site()
    power = next(r for r in tables.manifest() if r["path"] == f"sites/{site_id}/power_daily.csv")
    first, last = power["period"].split("/")
    return {"climate": {"source": "nasa_power", "first_day": first, "last_day": last, "seasons": len(tables.season_years())},
            "soil_calibration": {"current": tables.calibration_is_current(), "fitted_at": tables.calibration().get("point")},
            "note": label("location.note")}


def _status(session):
    counts = Counter(r["status"] for r in tables.provenance())
    simulated = session["outputs"]["main_screen"]["soil_water"]["is_simulated"]
    return {"mode": "demo" if simulated else "live", "badge": label("front.mode.demo" if simulated else "front.mode.live"),
            "simulated_inputs": ["sensor_readings"] if simulated else [],
            "exploratory": True, "validated_for_field": False, "disclaimer": label("screen.footer"),
            "simulated_reading": simulated,
            "values_by_status": dict(counts),
            "sources": [{"id": k, "title": v["title"], "publisher": v["publisher"]} for k, v in tables.sources().items()]}


def _missing(session):
    agronomist = session["inputs"]["agronomist"]
    missing = []
    if all(agronomist.get(k) is None for k in ("organic_matter_pct", "phosphorus_ppm", "ph")):
        missing.append(label("front.missing.soil_test"))
    return missing + [label("front.missing.calibrated_sensor"), label("front.missing.soil_diagnosis")]


def _water(session, generated_at):
    scenarios = session["outputs"]["main_screen"]["scenarios"]
    sensor = session["outputs"]["main_screen"]["soil_water"]
    state = scenarios["initial_state"]
    initial = state["water_levels"]["scenario_initial_water"]
    return {"mm": initial["value"], "capacity_mm": state["capacity_mm"], "source": "sensor", "reliability": "low",
            "updated_at": sensor.get("reading_date") or generated_at.isoformat(), "mm_status": initial["status"],
            "is_simulated": sensor["is_simulated"], "volumetric_moisture": sensor["volumetric_moisture"],
            "reading_moisture": sensor["raw_moisture"], "series": sensor["series"]}


def _detail(card):
    if card["kind"] == "rotation":
        return label("card.rotation_detail", crops=card["crops_modelled"], n=card["high_deficit_combinations"],
                     total=card["combinations"])
    status = card.get("status")
    if status in ("cycle_ended", "critical_stage_passed"):
        return label("card.cycle_ended" if status == "cycle_ended" else "card.stage_passed", day=card["day_of_cycle"],
                     cycle=card["cycle_days"])
    return label("card.deficit_reading", n=card["high_deficit_seasons"], total=card["scenarios"])


def _drops(card):
    split = card.get("split_in_10_parts")
    return {deficit.DROP_NAMES[k]: v for k, v in split.items()} if split else None


def _option(card):
    rotation = card["kind"] == "rotation"
    drops = _drops(card)
    sentence = label("front.sentence", out=drops["out"]) if drops else _detail(card)
    return {"id": card["id"], "name": card["title"], "is_current": card["is_current"], "water_risk": deficit.water_risk(drops),
            "drops": drops, "sentence": sentence, "soil_effect": None, "soil_reason": None, "why": None, "evidence": [],
            "benefits": [], "gaps": [w["label"] for w in card["warnings"]], "risks": [],
            "kind": card["kind"], "detail": _detail(card), "sowing": card.get("sowing"),
            "critical_window": card.get("critical_window"), "cycle_status": card.get("status"),
            "evaluated": card["combinations"] if rotation else card["scenarios"],
            "high_deficit": card["high_deficit_combinations"] if rotation else card.get("high_deficit_seasons"),
            "season_counts": card.get("season_counts"),
            "crops": [{"name": c["name"], "status": c["status"]} for c in card["crops"]] if rotation else [], "note": card.get("note")}


def summary(session, generated_at):
    return {"field": _field(), "mock": False, "generated_at": generated_at.isoformat(), "water": _water(session, generated_at),
            "soil": {"state": None, "trend": None, "precision": "low", "reasons": [], "missing": _missing(session)},
            "options": [_option(c) for c in session["outputs"]["option_cards"]]}


def scenarios(session):
    seasons = [ws.season_name(y) for y in ws.SEASON_YEARS]
    options = []
    for card in session["outputs"]["option_cards"]:
        by_season = {c["season"]: deficit.DROP_NAMES[c["class"]] for c in card.get("season_classes") or []}
        options.append({"id": card["id"], "name": card["title"], "years": [by_season.get(s) for s in seasons] if by_season else []})
    return {"from_year": ws.SEASON_YEARS[0], "to_year": ws.SEASON_YEARS[-1], "options": options}


def inputs(session):
    given = session["inputs"]
    current, agronomist = given["current_crop"] or {}, given["agronomist"]
    return {"farmer": {"current_crop": {"crop": current.get("crop"), "sowing_day": current.get("sowing")},
                       "seasons": [{"season": s["season"], "crops": s["crops"], "rating": s["rating"], "yield_kg_ha": s["yield_kg_ha"],
                                    "confirmed": True} for s in given["past_seasons"]]},
            "agronomist": {"soil_test": {"date": agronomist.get("analysis_date"), "om_pct": agronomist.get("organic_matter_pct"),
                                         "p_bray_ppm": agronomist.get("phosphorus_ppm"), "ph": agronomist.get("ph")},
                           "erosion_t_ha_yr": agronomist.get("erosion_t_ha_yr"),
                           "soil_type": {"description": agronomist.get("soil_type"), "confirmed": agronomist.get("soil_type_confirmed")}}}


def catalog():
    """The closed lists the forms offer."""
    return {"crops": [{"id": c, "name": label(ps.crop_label_key(c))} for c in ps.CROP_CHOICES],
            "history_crops": [{"id": c, "name": label(ps.crop_label_key(c))} for c in ps.HISTORY_CROP_CHOICES],
            "ratings": [{"value": v, "label": label(f"screen.sheet.rating.{v}")} for v in (1, 2, 3, 4, 5)],
            "seasons": ps.SEASON_CHOICES,
            "modes": [{"id": m, "badge": label(f"front.mode.{m}"), "meaning": label(f"front.mode.meaning.{m}")} for m in MODES]}


def api_parts(session, generated_at):
    """What the API contract calls `summary` and `scenarios`; the worker stores them in `results`."""
    return {"summary": summary(session, generated_at), "scenarios": scenarios(session)}


def build(session, generated_at):
    return {"schema_version": SCHEMA_VERSION, "generated_at": generated_at.isoformat(), "site": _site(), "status": _status(session),
            "summary": summary(session, generated_at), "inputs": inputs(session), "scenarios": scenarios(session),
            "catalog": catalog()}


def build_error(error, generated_at):
    """The document the file holds when the analysis could not be built: the same envelope, the error instead of the results.

    `error` is an EngineError's `to_dict()`; any other failure is reported as `internal_error` without leaking its text."""
    known = {"code", "field", "message"} <= set(error)
    return {"schema_version": SCHEMA_VERSION, "generated_at": generated_at.isoformat(),
            "status": {"mode": "error", "badge": label("front.mode.error"),
                       "error": {"code": error["code"] if known else "internal_error", "field": error.get("field") if known else None,
                                 "message": error["message"] if known else "Unexpected failure while building the analysis"}}}


def dumps(document):
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
