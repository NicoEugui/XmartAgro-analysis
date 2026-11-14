"""Scenarios for a chosen crop and sowing date.

Question answered: "If I sow this crop on this date, how would the available water have evolved under
different historical climate conditions?" It is not a yield prediction or a recommendation.

For each historical season the real climate of that season is applied from the reading date: first to the
soil water given by the sensor reading (up to sowing), then to the crop from sowing to the end of its cycle.
Stages and the critical window are recomputed from the chosen date. No forecast and no future climate is
used: each scenario is one historical season's own climate. The cycle length is kept fixed (a later sowing
usually shortens it), and a date outside the documented window is allowed but flagged.

"""

import statistics as st
from datetime import timedelta

from . import crops_uy as cu
from . import deficit
from . import sensor_input as si
from . import tables
from . import water_model as wm
from . import water_scenarios as ws
from .errors import EngineError
from .i18n import label

STEP = ws.STEP
FAR_SOWING_DAYS = tables.constant("far_sowing_days")
METADATA = {"type": "exploratory_scenario", "validation": "not_validated", "applicable_to_field": False,
            "initial_state_source": si.SENSOR_SOURCE, "is_simulated_input": True, "is_forecast": False,
            "is_yield_prediction": False}


def sowing_warnings(crop, sowing):
    return [{"code": "cycle_length_fixed", "label": label("sowing.warning.fixed_cycle")}]


def days_until_sowing(sowing, reading):
    """Days from the reading date to the next occurrence of the sowing (month, day), on a non-leap reference year."""
    reading_day = ws.safe_date(2001, *reading)
    sowing_day = ws.safe_date(2001 + (1 if sowing < reading else 0), *sowing)
    return (sowing_day - reading_day).days


def far_sowing_warning(sowing, reading):
    days = days_until_sowing(sowing, reading)
    if days > FAR_SOWING_DAYS:
        return {"code": "sowing_far_from_reading", "days": days,
                "label": label("sowing.warning.far_from_reading", days=str(days))}
    return None


def evaluate_sowing(crop, sowing, reading_theta=si.SIMULATED_THETA, reading_date=ws.START,
                    params=None, weather=None, et0=None, source_info=None):
    """Scenario document for `crop` sown on `sowing` (month, day), given a reading taken on `reading_date`."""
    spec = cu.require_crop(crop)
    if spec.get("perennial"):
        raise EngineError("perennial_crop_has_no_sowing_date", "crop",
                          f"'{crop}' is a perennial pasture and has no sowing date",
                          crop=crop)
    sowing = ws.validate_month_day(sowing, "sowing")
    reading_date = ws.validate_month_day(reading_date, "reading_date")
    theta = si.validate_theta(reading_theta)
    if params is None:
        calibration = wm.load_calibration()
        params = [calibration["parameters"][k] for k in wm.PARAMS]
    weather = weather or wm.load_power()
    wm.validate_weather(weather)
    et0 = et0 or wm.precompute_et0(weather)
    capacity, p, cycle = params[1], spec["p"], cu.cycle_days(crop)
    first, last = min(weather), max(weather)

    rows, skipped, trajectories, gaps = [], [], [], []
    for year in ws.SEASON_YEARS:
        reading_day = ws.safe_date(year, *reading_date)
        sowing_year = year + (1 if sowing < reading_date else 0)
        sowing_day = ws.safe_date(sowing_year, *sowing)
        end = sowing_day + timedelta(days=cycle - 1)
        if reading_day < first or end > last or not wm.has_all_days(weather, reading_day, end):
            skipped.append({"season": ws.season_name(sowing_year), "reason": "window_outside_climate_record"})
            continue
        if sowing_day > reading_day:  # the sensor state is carried to the sowing date by that season's own climate
            moisture = wm.simulate_moisture(params, weather, et0, reading_day, sowing_day - timedelta(days=1), theta)
            water0 = min(capacity, max(0.0, (moisture[sowing_day - timedelta(days=1)] - params[0]) * wm.ROOT_DEPTH_MM))
        else:
            water0 = si.to_available_water_mm(theta, params)
        days = wm.simulate_water_balance(params, weather, et0, sowing_day, end, water0,
                                         lambda d, s=sowing_day: cu.kc_on_day(crop, s, d), lambda d: 1 - p)
        a, b = cu.critical_window_from_sowing(crop, sowing_day)
        window = [r for r in days if a <= r["day"] <= b]
        demand = sum(r["demand_mm"] for r in window)
        stress = 1 - sum(r["actual_mm"] for r in window) / demand
        rows.append({"season": ws.season_name(sowing_year), "sowing_date": str(sowing_day),
                     "water_at_sowing_mm": round(water0, 1), "stress": round(stress, 3),
                     "deficit_days": sum(r["unmet_mm"] > 1 for r in window),
                     "deficit_mm": round(sum(r["unmet_mm"] for r in window), 1), "class": deficit.classify(stress)})
        trajectories.append([r["water_mm"] for r in days])
        gaps.append((sowing_day - reading_day).days)
    if not rows:
        raise EngineError("no_complete_season", "sowing",
                          "No historical season has a complete window inside the climate record for this date and crop")
    counts = {c: sum(r["class"] == c for r in rows) for c in deficit.CLASSES}
    offsets = range(0, cycle, STEP)
    spread = [{"day_after_sowing": o,
               "p10_mm": round(ws.percentile([t[o] for t in trajectories], 0.10), 1),
               "median_mm": round(ws.percentile([t[o] for t in trajectories], 0.50), 1),
               "p90_mm": round(ws.percentile([t[o] for t in trajectories], 0.90), 1)} for o in offsets]
    initial_window = cu.critical_window_from_sowing(crop, ws.safe_date(2001, *sowing))
    info = source_info or {"source": si.SENSOR_SOURCE, "is_simulated": True}
    return {
        "metadata": {**METADATA, "initial_state_source": info["source"], "is_simulated_input": info["is_simulated"]},
        "question": label("sowing.note.question"),
        "crop": {"id": crop, "name": label(cu.name_label_key(crop)), "cycle_days": cycle,
                 "critical_window_days_after_sowing": [
                     (initial_window[0] - ws.safe_date(2001, *sowing)).days,
                     (initial_window[1] - ws.safe_date(2001, *sowing)).days]},
        "sowing": f"{sowing[0]:02d}-{sowing[1]:02d}",
        "reading": {"date": f"{reading_date[0]:02d}-{reading_date[1]:02d}", "volumetric_moisture": theta,
                    "is_simulated": info["is_simulated"], "warnings": si.reading_warnings(theta, params),
                    "median_days_to_sowing": int(st.median(gaps))},
        "warnings": sowing_warnings(crop, sowing) + ([far] if (far := far_sowing_warning(sowing, reading_date)) else []),
        "no_future_information": label("sowing.note.no_future_info"),
        "mm_note": label("sowing.note.water_mm"),
        "scenarios": len(rows), "seasons_skipped": skipped,
        "season_counts": counts, "split_in_10_parts": deficit.split_in_10(counts, len(rows)),
        "median_water_at_sowing_mm": round(st.median(r["water_at_sowing_mm"] for r in rows), 1),
        "median_stress": round(st.median(r["stress"] for r in rows), 3),
        "season_results": rows,
        "water_after_sowing": spread,
        "uncertainty": {"covers": ["climate_variability_between_historical_seasons"],
                        "does_not_cover": ["soil_parameters", "sensor_reading", "model_parameters"],
                        "is_confidence_interval": False, "note": label("scenarios.uncertainty_note")},
    }


def last_sowing_on_or_before(sowing, reading, year):
    """The most recent occurrence of the (month, day) sowing date on or before the reading date of `year`."""
    reading_day = ws.safe_date(year, *reading)
    sowing_day = ws.safe_date(year, *sowing)
    if sowing_day > reading_day:
        sowing_day = ws.safe_date(year - 1, *sowing)
    return sowing_day, reading_day


def evaluate_current_crop(crop, sowing, reading_theta=si.SIMULATED_THETA, reading_date=ws.START,
                          params=None, weather=None, et0=None, source_info=None):
    """A crop that is already sown: simulate from today's reading to the end of its cycle.

    The sowing date is in the past (the most recent one on or before the reading date). The crop is at day d of its
    cycle; each historical season's climate is applied from the reading date with the coefficients of that stage.
    If the cycle has ended, or the critical stage has already passed, there is nothing to simulate and the status
    says so instead of inventing a future sowing.
    """
    spec = cu.require_crop(crop)
    if spec.get("perennial"):
        raise EngineError("perennial_crop_has_no_sowing_date", "crop",
                          f"'{crop}' is a perennial pasture and has no sowing date", crop=crop)
    sowing = ws.validate_month_day(sowing, "sowing")
    reading_date = ws.validate_month_day(reading_date, "reading_date")
    theta = si.validate_theta(reading_theta)
    if params is None:
        calibration = wm.load_calibration()
        params = [calibration["parameters"][k] for k in wm.PARAMS]
    weather = weather or wm.load_power()
    wm.validate_weather(weather)
    et0 = et0 or wm.precompute_et0(weather)
    cycle, p = cu.cycle_days(crop), spec["p"]
    info = source_info or {"source": si.SENSOR_SOURCE, "is_simulated": True}
    ref_sowing, ref_reading = last_sowing_on_or_before(sowing, reading_date, 2001)
    day = (ref_reading - ref_sowing).days
    start, end = cu.critical_window_from_sowing(crop, ref_sowing)
    win_start, win_end = (start - ref_sowing).days, (end - ref_sowing).days
    base = {
        "metadata": {**METADATA, "initial_state_source": info["source"], "is_simulated_input": info["is_simulated"]},
        "crop": {"id": crop, "name": label(cu.name_label_key(crop)), "cycle_days": cycle,
                 "critical_window_days_after_sowing": [win_start, win_end]},
        "sowing": f"{sowing[0]:02d}-{sowing[1]:02d}", "is_current_crop": True, "day_of_cycle": day,
        "reading": {"date": f"{reading_date[0]:02d}-{reading_date[1]:02d}", "volumetric_moisture": theta,
                    "is_simulated": info["is_simulated"], "warnings": si.reading_warnings(theta, params)},
        "warnings": [w for w in sowing_warnings(crop, sowing) if w["code"] != "cycle_length_fixed"]
                    + [{"code": "current_crop_partial_cycle", "label": label("sowing.warning.current_partial")}],
        "no_future_information": label("sowing.note.no_future_info"), "mm_note": label("sowing.note.water_mm"),
    }
    if day >= cycle:
        return {**base, "warnings": base["warnings"][:-1], "status": "cycle_ended", "scenarios": 0, "season_counts": None, "split_in_10_parts": None}
    if win_end < day:
        return {**base, "warnings": base["warnings"][:-1], "status": "critical_stage_passed", "scenarios": 0, "season_counts": None, "split_in_10_parts": None}
    remaining = cycle - day
    first_offset = max(win_start, day)
    fraction = (win_end - first_offset + 1) / (win_end - win_start + 1)
    water0 = si.to_available_water_mm(theta, params)
    rows, skipped, trajectories = [], [], []
    for year in ws.SEASON_YEARS:
        reading_day = ws.safe_date(year, *reading_date)
        sowing_day = reading_day - timedelta(days=day)
        finish = reading_day + timedelta(days=remaining - 1)
        if reading_day < min(weather) or finish > max(weather) or not wm.has_all_days(weather, reading_day, finish):
            skipped.append({"season": ws.season_name(year), "reason": "window_outside_climate_record"})
            continue
        days = wm.simulate_water_balance(params, weather, et0, reading_day, finish, water0,
                                         lambda d, s=sowing_day: cu.kc_on_day(crop, s, d), lambda d: 1 - p)
        window = [r for r in days if sowing_day + timedelta(days=first_offset) <= r["day"] <= sowing_day + timedelta(days=win_end)]
        demand = sum(r["demand_mm"] for r in window)
        stress = 1 - sum(r["actual_mm"] for r in window) / demand
        rows.append({"season": ws.season_name(year), "stress": round(stress, 3),
                     "deficit_days": sum(r["unmet_mm"] > 1 for r in window),
                     "deficit_mm": round(sum(r["unmet_mm"] for r in window), 1), "class": deficit.classify(stress)})
        trajectories.append([r["water_mm"] for r in days])
    if not rows:
        raise EngineError("no_complete_season", "sowing",
                          "No historical season has a complete window inside the climate record for this crop and date")
    counts = {c: sum(r["class"] == c for r in rows) for c in deficit.CLASSES}
    return {**base, "status": "in_critical_stage" if day >= win_start else "critical_stage_ahead",
            "remaining_days": remaining, "critical_stage_remaining_fraction": round(fraction, 3),
            "scenarios": len(rows), "seasons_skipped": skipped, "season_counts": counts,
            "split_in_10_parts": deficit.split_in_10(counts, len(rows)), "season_results": rows,
            "water_after_reading": [{"day": o, "median_mm": round(ws.percentile([t[o] for t in trajectories], 0.5), 1)}
                                    for o in range(0, remaining, STEP)],
            "uncertainty": {"covers": ["climate_variability_between_historical_seasons"],
                            "does_not_cover": ["soil_parameters", "sensor_reading", "model_parameters"],
                            "is_confidence_interval": False, "note": label("scenarios.uncertainty_note")}}


def compare_sowing_dates(crop, dates, **kwargs):
    """Summaries for several sowing dates of one crop; differences are exploratory, never a recommendation."""
    out = []
    for date_ in dates:
        d = evaluate_sowing(crop, date_, **kwargs)
        out.append({"sowing": d["sowing"], "scenarios": d["scenarios"], "season_counts": d["season_counts"],
                    "median_water_at_sowing_mm": d["median_water_at_sowing_mm"], "median_stress": d["median_stress"],
                    "warnings": [w["code"] for w in d["warnings"]]})
    return {"crop": crop, "robust_comparison": False, "dates": out}
