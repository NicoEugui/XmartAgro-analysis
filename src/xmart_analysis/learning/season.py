"""Water stress of one crop season: the one function the pipeline (the model's soil and crop) and the simulated truth share."""

from datetime import timedelta

from ..engine import crops_uy as cu
from ..engine import tables
from ..engine import water_model as wm


def water_at(params, sowing, weather, et0):
    """Available water (mm) the soil holds on the sowing day after a spin-up with that season's own climate (what a sensor would read), or None
    if the climate record does not reach back that far."""
    spin = sowing - timedelta(days=tables.constant("learn_spinup_days"))
    if spin < min(weather) or sowing > max(weather):
        return None
    moisture = wm.simulate_moisture(params, weather, et0, spin, sowing - timedelta(days=1), tables.constant("learn_start_theta"))
    return wm.water_from_theta(moisture[sowing - timedelta(days=1)], params[0], params[1])


def stress(params, spec, crop, sowing, weather, et0, start_water_mm=None):
    """Unmet share of the crop's demand in its critical stage (0 none, 1 all), or None if the climate record does not cover the season.

    The season starts from the water its own climate left (`water_at`), the same for model and truth, unless `start_water_mm` says where it
    starts: a scenario applies another season's climate to the water of today."""
    end = sowing + timedelta(days=cu.cycle_days(crop, spec) - 1)
    water0 = water_at(params, sowing, weather, et0) if start_water_mm is None else start_water_mm
    if water0 is None or end > max(weather):
        return None
    days = wm.simulate_water_balance(params, weather, et0, sowing, end, water0, lambda d: cu.kc_on_day(crop, sowing, d, spec),
                                     lambda d: 1 - spec["p"])
    first, last = cu.critical_window_from_sowing(crop, sowing, spec)
    window = [r for r in days if first <= r["day"] <= last]
    demand = sum(r["demand_mm"] for r in window)
    return 1 - sum(r["actual_mm"] for r in window) / demand
