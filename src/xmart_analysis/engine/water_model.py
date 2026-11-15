"""Daily soil water balance (bucket model) for the demo point.

The bucket stores water in the root zone (1 m). Rain enters; evapotranspiration and drainage leave.
Its parameters are not assumed: they are calibrated against SMAP L4 root-zone moisture
(see calibrate_model.py). L4 is a 9 km model product, not a measurement of the field.
"""

import csv
import json
import math
from datetime import date, timedelta

from . import tables
from .errors import EngineError

POWER_CSV = tables.site_file("power_daily.csv")  # the climate of the active site
CALIBRATION_PATH = tables.calibration_path()
ROOT_DEPTH_MM = tables.constant("root_depth_mm")
LATITUDE = tables.constant("latitude")
PARAMS = ("theta_min", "capacity_mm", "kc", "stress_threshold", "drainage_onset_fraction", "daily_drainage")


def load_calibration():
    return json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))


def reference_et(day, weather):
    """Reference evapotranspiration (mm/day), Hargreaves with extraterrestrial radiation from latitude."""
    latitude = math.radians(LATITUDE)
    angle = 2 * math.pi * day.timetuple().tm_yday / 365
    declination = 0.409 * math.sin(angle - 1.39)
    sunset = math.acos(-math.tan(latitude) * math.tan(declination))
    radiation = (24 * 60 / math.pi) * 0.0820 * (1 + 0.033 * math.cos(angle)) * (
        sunset * math.sin(latitude) * math.sin(declination)
        + math.cos(latitude) * math.cos(declination) * math.sin(sunset)
    )
    spread = weather["T2M_MAX"] - weather["T2M_MIN"]
    return max(0, 0.0023 * 0.408 * radiation * (weather["T2M"] + 17.8) * math.sqrt(spread))


def load_power(path=POWER_CSV):
    """Daily UTC climate: {date: {PRECTOTCORR, T2M, T2M_MIN, T2M_MAX}}."""
    table = path.read_text().split("-END HEADER-", 1)[1]
    weather = {}
    for row in csv.DictReader(table.strip().splitlines()):
        day = date(int(row["YEAR"]), 1, 1) + timedelta(days=int(row["DOY"]) - 1)
        values = {k: float(row[k]) for k in ("PRECTOTCORR", "T2M", "T2M_MIN", "T2M_MAX")}
        if any(v == -999 for v in values.values()):
            raise EngineError("invalid_climate_data", "climate", f"Missing value in POWER data: {day}", day=str(day))
        weather[day] = values
    return weather


def rain_between(weather, start, end_exclusive):
    """Accumulated rain (mm) from start up to, not including, end_exclusive. Fails if a day is missing."""
    days = (end_exclusive - start).days
    total = 0.0
    for i in range(days):
        day = start + timedelta(days=i)
        if day not in weather:
            raise EngineError("missing_climate_day", "climate", f"No climate record for {day}", day=str(day))
        total += weather[day]["PRECTOTCORR"]
    return total


def validate_weather(weather):
    """Reject inconsistent climate data (negative rain, NaN, minimum above maximum temperature, missing fields)."""
    if not weather:
        raise EngineError("invalid_climate_data", "climate", "The climate record is empty")
    for day, w in weather.items():
        for key in ("PRECTOTCORR", "T2M", "T2M_MIN", "T2M_MAX"):
            value = w.get(key)
            if value is None or isinstance(value, bool) or value != value or value in (float("inf"), float("-inf")):
                raise EngineError("invalid_climate_data", "climate", f"{key} is missing or not finite on {day}", day=str(day))
        if w["PRECTOTCORR"] < 0:
            raise EngineError("invalid_climate_data", "climate", f"Negative rain on {day}", day=str(day))
        if w["T2M_MIN"] > w["T2M_MAX"]:
            raise EngineError("invalid_climate_data", "climate", f"Minimum temperature above maximum on {day}", day=str(day))


def has_all_days(weather, start, end_inclusive):
    return all(start + timedelta(days=i) in weather for i in range((end_inclusive - start).days + 1))


def precompute_et0(weather):
    return {day: reference_et(day, w) for day, w in weather.items()}


def water_from_theta(theta, theta_min, capacity):
    """Available water (mm) the bucket holds at a volumetric moisture, between empty and full."""
    return min(capacity, max(0.0, (theta - theta_min) * ROOT_DEPTH_MM))


def nudge(water, observed_water, gain):
    """Move the modelled water part of the way to an observed value: gain 0 ignores it, gain 1 adopts it."""
    return water + gain * (observed_water - water)


def daily_step(params, water, rain, et0_day, kc, stress_at=None):
    """One day of the bucket: rain in, drainage and overflow out, then evapotranspiration reduced by water stress.

    stress_at is the fraction of capacity below which the crop suffers; without it the calibrated threshold is used.
    Returns the closing water and the day's flows (mm): loss, demand and actual evapotranspiration.
    """
    _theta_min, capacity, _kc, stress_calibrated, drainage_onset, drain = params
    water += rain
    before_loss = water
    onset_mm = drainage_onset * capacity
    if water > onset_mm:
        water -= drain * (water - onset_mm)
    if water > capacity:
        water = capacity
    threshold = (stress_calibrated if stress_at is None else stress_at) * capacity
    stress = 1.0 if water >= threshold else water / threshold
    demand = et0_day * kc
    actual = min(water, demand * stress)
    return water - actual, {"loss_mm": before_loss - water, "demand_mm": demand, "actual_mm": actual}


def simulate_water_balance(params, weather, et0, start, end, initial_water_mm, kc_fn, stress_fn=None):
    """Daily balance with a crop coefficient per date; returns detailed daily rows.

    kc_fn(date) gives the coefficient of whatever occupies the soil that day. stress_fn(date), if
    given, gives the fraction of capacity below which the crop starts to suffer (1 - p);
    without it the threshold calibrated against L4 is used. Each row has the closing water, demand,
    actual evapotranspiration, unmet demand, drainage/overflow loss and rain (all in mm).
    """
    water = min(params[1], max(0.0, initial_water_mm))
    rows = []
    day = start
    while day <= end:
        rain = weather[day]["PRECTOTCORR"]
        water, flows = daily_step(params, water, rain, et0[day], kc_fn(day), None if stress_fn is None else stress_fn(day))
        rows.append({"day": day, "water_mm": water, "demand_mm": flows["demand_mm"], "actual_mm": flows["actual_mm"],
                     "unmet_mm": flows["demand_mm"] - flows["actual_mm"], "loss_mm": flows["loss_mm"], "rain_mm": rain})
        day += timedelta(days=1)
    return rows


def simulate_moisture(params, weather, et0, start, end, initial_theta, kc_by_day=None, observations=None, gain=0.0):
    """Simulate day by day; returns {date: volumetric moisture m3/m3}.

    kc_by_day allows a crop coefficient per date; without it the calibrated kc (mixed cover of the
    L4 pixel) is used. observations ({date: moisture reading}) corrects the modelled water at the end of each day that
    has one, by `gain` (see nudge); without them the run is open-loop.
    """
    theta_min, capacity, kc = params[0], params[1], params[2]
    water = water_from_theta(initial_theta, theta_min, capacity)
    out = {}
    day = start
    while day <= end:
        water, _ = daily_step(params, water, weather[day]["PRECTOTCORR"], et0[day], kc if kc_by_day is None else kc_by_day(day))
        if observations and day in observations:
            water = nudge(water, water_from_theta(observations[day], theta_min, capacity), gain)
        out[day] = theta_min + water / ROOT_DEPTH_MM
        day += timedelta(days=1)
    return out
