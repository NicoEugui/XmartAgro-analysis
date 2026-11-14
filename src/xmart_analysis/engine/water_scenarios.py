"""Water scenarios from the current sensor reading.

For each historical season (1987-2025) the real, continuous climate of that season, starting on the
same calendar date, is applied to today's soil water for `horizon` days. The result is a spread of water
trajectories, not a forecast: the fractions are shares of historical climates, not probabilities, and the
band is not a confidence interval.

Initial state: the sensor reading (simulated for now) converted with assumed soil parameters. Invalid
readings are rejected; readings outside the assumed soil bounds are kept but flagged. Seasons whose window
falls outside the available climate record are skipped and reported. Structural sensitivity: the same
seasons with a shifted wilting point and a scaled water capacity, keeping only physically plausible soils
and comparing them in volumetric moisture.
"""

import statistics as st
from datetime import date, timedelta

from . import sensor_input as si
from . import water_model as wm
from . import tables
from .errors import EngineError
from .i18n import label

START = tables.month_day("default_reading")  # reference date of the reading
HORIZON_DAYS = tables.constant("scenario_horizon_days")
STEP = tables.constant("scenario_step_days")
SEASON_YEARS = tables.season_years()
METADATA = {"type": "exploratory_scenario", "validation": "not_validated", "applicable_to_field": False,
            "initial_state_source": si.SENSOR_SOURCE, "is_simulated_input": True}
# Physical plausibility ranges (team assumptions) for the structural sensitivity.
WILTING_RANGE = (tables.constant("wilting_min"), tables.constant("wilting_max"))
FIELD_CAPACITY_RANGE = (tables.constant("field_capacity_min"), tables.constant("field_capacity_max"))
AVAILABLE_WATER_RANGE_MM = (tables.constant("available_water_min"), tables.constant("available_water_max"))
CAPACITY_SCALES = tables.constant("sensitivity_capacity_scales")
WILTING_SHIFTS = tables.constant("sensitivity_wilting_shifts")


def percentile(values, q):
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def season_name(year):
    return f"{year}/{(year + 1) % 100:02d}"


def safe_date(year, month, day):
    """A calendar date; 29 February falls back to 28 February in non-leap years."""
    try:
        return date(year, month, day)
    except (ValueError, TypeError):
        if month == 2 and day == 29:
            return date(year, 2, 28)
        raise EngineError("invalid_date", "date", f"{year}-{month}-{day} is not a calendar date",
                          year=year, month=month, day=day)


def validate_month_day(value, field):
    """Check a (month, day) pair; returns it as a tuple of ints (29 February is allowed)."""
    try:
        month, day = value
        date(2000, month, day)  # 2000 is a leap year
    except (ValueError, TypeError):
        raise EngineError("invalid_date", field, f"{field} must be a valid (month, day) pair, got {value!r}",
                          received=repr(value)) from None
    return (month, day)


def plausibility(params, sensor_theta):
    """Return the list of violated physical constraints (empty if the soil is plausible)."""
    wilting, capacity = params[0], params[1]
    field_capacity = wilting + capacity / wm.ROOT_DEPTH_MM
    reasons = []
    if not WILTING_RANGE[0] <= wilting <= WILTING_RANGE[1]:
        reasons.append("wilting_point_out_of_range")
    if not FIELD_CAPACITY_RANGE[0] <= field_capacity <= FIELD_CAPACITY_RANGE[1]:
        reasons.append("field_capacity_out_of_range")
    if not AVAILABLE_WATER_RANGE_MM[0] <= capacity <= AVAILABLE_WATER_RANGE_MM[1]:
        reasons.append("available_water_out_of_range")
    if sensor_theta < wilting:
        reasons.append("sensor_below_wilting_point")
    return reasons


def usable_seasons(weather, start=START, horizon=HORIZON_DAYS):
    """Split SEASON_YEARS into seasons whose whole window is in the climate record and the skipped ones."""
    first, last = min(weather), max(weather)
    used, skipped = [], []
    for year in SEASON_YEARS:
        begin = safe_date(year, *start)
        end = begin + timedelta(days=horizon)
        if begin >= first and end <= last and wm.has_all_days(weather, begin, end):
            used.append(year)
        else:
            skipped.append(year)
    return used, skipped


def trajectories(params, weather, et0, initial_theta, start=START, horizon=HORIZON_DAYS):
    """{year: (start_date, [theta per day for 0..horizon])}; each uses one continuous climate sequence."""
    out = {}
    used, _ = usable_seasons(weather, start, horizon)
    for year in used:
        begin = safe_date(year, *start)
        theta = wm.simulate_moisture(params, weather, et0, begin, begin + timedelta(days=horizon), initial_theta)
        out[year] = (begin, [theta[begin + timedelta(days=i)] for i in range(horizon + 1)])
    if not out:
        raise EngineError("no_complete_season", "horizon_days",
                          "No historical season has a complete window inside the climate record; reduce the horizon")
    return out


def spread(trajs, params, horizon=HORIZON_DAYS):
    """Percentiles at the same horizon day across scenarios, in mm of available water and in m3/m3."""
    rows = []
    for offset in range(0, horizon + 1, STEP):
        thetas = [t[offset] for _, t in trajs.values()]
        mm = [si.to_available_water_mm(x, params) for x in thetas]
        rows.append({"day": offset,
                     "p10_mm": round(percentile(mm, 0.10), 1), "median_mm": round(percentile(mm, 0.50), 1),
                     "p90_mm": round(percentile(mm, 0.90), 1),
                     "p10_m3_m3": round(percentile(thetas, 0.10), 4), "median_m3_m3": round(percentile(thetas, 0.50), 4),
                     "p90_m3_m3": round(percentile(thetas, 0.90), 4)})
    return rows


def structural_sensitivity(params, weather, et0, initial_theta, start=START, horizon=HORIZON_DAYS):
    """Second sensitivity test: shift the wilting point and scale the water capacity (field capacity / depth)."""
    configs = []
    for scale in CAPACITY_SCALES:
        for shift in WILTING_SHIFTS:
            p = list(params)
            p[0] = params[0] + shift
            p[1] = params[1] * scale
            reasons = plausibility(p, initial_theta)
            entry = {"capacity_scale": scale, "wilting_point_shift_m3_m3": shift,
                     "wilting_point_m3_m3": round(p[0], 4), "field_capacity_m3_m3": round(p[0] + p[1] / wm.ROOT_DEPTH_MM, 4),
                     "capacity_mm": round(p[1], 1), "plausible": not reasons, "violations": reasons}
            if not reasons:
                trajs = trajectories(p, weather, et0, initial_theta, start, horizon)
                entry["initial_water_mm"] = round(si.to_available_water_mm(initial_theta, p), 1)
                entry["by_day"] = {r["day"]: r for r in spread(trajs, p, horizon)}
            configs.append(entry)
    plausible = [c for c in configs if c["plausible"]]
    base = {"configurations": len(configs), "plausible_configurations": len(plausible),
            "excluded": [{"capacity_scale": c["capacity_scale"], "wilting_point_shift_m3_m3": c["wilting_point_shift_m3_m3"],
                          "violations": c["violations"]} for c in configs if not c["plausible"]],
            "varied": {"capacity_scale": list(CAPACITY_SCALES), "wilting_point_shift_m3_m3": list(WILTING_SHIFTS)},
            "plausibility_note": label("scenarios.plausibility_note"),
            "comparable_unit_note": label("scenarios.structural_comparable"),
            "configuration_details": [{k: v for k, v in c.items() if k != "by_day"} for c in configs],
            "is_confidence_interval": False, "note": label("scenarios.structural_note")}
    if not plausible:
        return {**base, "status": "no_plausible_configuration", "initial_water_range_mm": None,
                "envelope_by_day_m3_m3": None}
    days = [d for d in (28, 56, 84, 119) if d in plausible[0]["by_day"]]
    envelope = [{"day": d,
                 "p10_min_m3_m3": min(c["by_day"][d]["p10_m3_m3"] for c in plausible),
                 "median_min_m3_m3": min(c["by_day"][d]["median_m3_m3"] for c in plausible),
                 "median_max_m3_m3": max(c["by_day"][d]["median_m3_m3"] for c in plausible),
                 "p90_max_m3_m3": max(c["by_day"][d]["p90_m3_m3"] for c in plausible)} for d in days]
    return {**base, "status": "ok",
            "initial_water_range_mm": [min(c["initial_water_mm"] for c in plausible),
                                       max(c["initial_water_mm"] for c in plausible)],
            "envelope_by_day_m3_m3": envelope}


def _source_key(base, info):
    """Label key for a sensor-dependent text: the simulated sensor keeps the base key, other sources have their own."""
    return base if info["is_simulated"] else f"{base}.{info['source']}"


def build_scenarios(initial_theta=si.SIMULATED_THETA, start=START, horizon=HORIZON_DAYS,
                    params=None, weather=None, et0=None, source_info=None):
    """Full scenario document (language-neutral, with label objects) for any valid reading, date and horizon."""
    theta = si.validate_theta(initial_theta)
    start = validate_month_day(start, "start")
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < STEP or horizon > 1000:
        raise EngineError("horizon_out_of_range", "horizon_days",
                          f"Horizon must be an integer between {STEP} and 1000 days, got {horizon!r}",
                          received=repr(horizon), minimum=STEP, maximum=1000)
    if params is None:
        calibration = wm.load_calibration()
        params = [calibration["parameters"][k] for k in wm.PARAMS]
    weather = weather or wm.load_power()
    wm.validate_weather(weather)
    et0 = et0 or wm.precompute_et0(weather)
    capacity = params[1]
    initial_mm = si.to_available_water_mm(theta, params)
    threshold_mm = params[3] * capacity  # level below which the calibrated balance restricts evapotranspiration

    trajs = trajectories(params, weather, et0, theta, start, horizon)
    band = spread(trajs, params, horizon)
    _, skipped = usable_seasons(weather, start, horizon)
    mm_by_year = {y: [si.to_available_water_mm(x, params) for x in t] for y, (_, t) in trajs.items()}
    check_days = [d for d in (30, 60, 90, 120) if d <= horizon]
    below = {str(o): sum(t[o] < threshold_mm for t in mm_by_year.values()) for o in check_days}
    index = [{"season": season_name(y), "start_date": str(begin), "end_date": str(begin + timedelta(days=horizon)),
              "minimum_mm": round(min(mm_by_year[y]), 1), "day_of_minimum": mm_by_year[y].index(min(mm_by_year[y])),
              "final_mm": round(mm_by_year[y][-1], 1),
              "rain_mm": round(wm.rain_between(weather, begin, begin + timedelta(days=horizon + 1)), 1)}
             for y, (begin, _) in trajs.items()]
    lowest_water = sorted(index, key=lambda r: r["minimum_mm"])[:5]  # depends on the reading and on when the dry spell falls
    driest_by_rain = sorted(index, key=lambda r: r["rain_mm"])[:5]
    info = source_info or {"source": si.SENSOR_SOURCE, "is_simulated": True}
    return {
        "metadata": {**METADATA, "initial_state_source": info["source"], "is_simulated_input": info["is_simulated"]},
        "note": label("scenarios.note"),
        "initial_state": {
            "sensor": si.soil_water_block(theta, source_info),
            "reading_warnings": si.reading_warnings(theta, params),
            "reading_as_received_m3_m3": theta,
            "reading_used_by_model_m3_m3": round(min(max(theta, params[0]), params[0] + capacity / wm.ROOT_DEPTH_MM), 4),
            "water_levels": {
                "current_volumetric_moisture": {"value": theta, "unit": "m3/m3",
                                                "status": "simulated" if info["is_simulated"] else "received_unvalidated",
                                                "label": label(_source_key("scenarios.level.volumetric", info))},
                "current_available_water": {"value": None, "unit": "mm", "status": "not_determined",
                                            "label": label("scenarios.level.available")},
                "scenario_initial_water": {"value": round(initial_mm, 1), "unit": "mm",
                                           "status": "derived_from_assumptions",
                                           "label": label("scenarios.level.scenario")}},
            "display_rule": label("scenarios.display_rule"),
            "capacity_mm": round(capacity, 1), "note": label(_source_key("scenarios.initial_state", info))},
        "start": f"{start[0]:02d}-{start[1]:02d}",
        "horizon_days": horizon, "scenarios": len(trajs),
        "seasons_skipped": [{"season": season_name(y), "reason": "window_outside_climate_record"} for y in skipped],
        "stress_threshold_mm": round(threshold_mm, 1),
        "spread_label": label("scenarios.spread_label"),
        "uncertainty": {"covers": ["climate_variability_between_historical_seasons"],
                        "does_not_cover": ["soil_parameters", "sensor_reading", "model_parameters"],
                        "is_confidence_interval": False, "note": label("scenarios.uncertainty_note")},
        "spread_by_day": band,
        "scenario_index": index,
        "structural_sensitivity": structural_sensitivity(params, weather, et0, theta, start, horizon),
        "scenarios_below_threshold_by_day": below,
        "lowest_water_scenarios": [r["season"] for r in lowest_water],
        "driest_by_rain_scenarios": [r["season"] for r in driest_by_rain],
        "median_minimum_mm": round(st.median(r["minimum_mm"] for r in index), 1),
        "limitations": [label("scenarios.limit.fallow"), label("method.limit.single_capacity"),
                        label("method.limit.correlations")],
    }
