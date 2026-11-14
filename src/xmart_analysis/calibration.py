"""Calibrate the water balance against NASA SMAP L4 root-zone moisture and validate on years it has not seen.

Needs scipy (extra `calibrate`). L4 is a 9 km model product, not a measurement of the field. The evaporative demand is the
corrected one (`et0_scale`), so the soil parameters must be refitted whenever that scale changes.
"""

import hashlib
import math
from datetime import timedelta
from pathlib import Path
from statistics import mean

from .engine import tables
from .engine import water_model as wm
from .validation import smap

CALIBRATION_PERIOD = smap.PERIODS["calibration"]
VALIDATION_PERIOD = smap.PERIODS["validation"]
LIMITATIONS = ["L4 is a model product at 9 km, not a measurement of the field",
               "the calibrated Kc represents mixed cover, not a crop",
               "the parameters may absorb errors in the POWER rainfall"]


def days(a, b):
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


def metrics(sim, obs, period):
    keys = [d for d in days(*period) if d in obs and d in sim]
    s, o = [sim[d] for d in keys], [obs[d] for d in keys]
    ms, mo = mean(s), mean(o)
    corr = sum((a - ms) * (b - mo) for a, b in zip(s, o)) / math.sqrt(sum((a - ms) ** 2 for a in s) * sum((b - mo) ** 2 for b in o))
    clim_o, clim_s = {}, {}
    for d, a, b in zip(keys, s, o):  # remove the mean seasonal cycle so the season alone is not rewarded
        clim_o.setdefault(d.timetuple().tm_yday // 15, []).append(b)
        clim_s.setdefault(d.timetuple().tm_yday // 15, []).append(a)
    an_o = [b - mean(clim_o[d.timetuple().tm_yday // 15]) for d, b in zip(keys, o)]
    an_s = [a - mean(clim_s[d.timetuple().tm_yday // 15]) for d, a in zip(keys, s)]
    anomaly = sum(a * b for a, b in zip(an_s, an_o)) / math.sqrt(sum(a * a for a in an_s) * sum(b * b for b in an_o))
    return {"days": len(keys), "rmse_m3_m3": round(math.sqrt(mean((a - b) ** 2 for a, b in zip(s, o))), 4),
            "bias_m3_m3": round(ms - mo, 4), "correlation": round(corr, 3), "anomaly_correlation": round(anomaly, 3)}


def search_bounds():
    """Soil parameters are searched only inside the physically plausible ranges the scenarios later enforce."""
    fixed = {"theta_min": (tables.constant("wilting_min"), tables.constant("wilting_max")),
             "capacity_mm": (tables.constant("available_water_min"), tables.constant("available_water_max"))}
    previous = tables.calibration()["search_bounds"]
    return [tuple(fixed.get(name, previous[name])) for name in wm.PARAMS]


def calibrate(l4_path, seeds=(7, 1, 2, 3, 4), maxiter=60, popsize=14):
    """Fit the soil parameters with several seeds and keep the lowest calibration error (validation years are not used to
    choose). The spread across seeds is reported: different parameter sets can fit SMAP L4 equally well."""
    from scipy.optimize import differential_evolution

    weather, l4 = wm.load_power(), smap.load_l4(l4_path)
    et0 = wm.precompute_et0(weather)
    start, end = CALIBRATION_PERIOD
    initial = l4[start]
    fit_days = [d for d in days(start, end) if d in l4]
    bounds = search_bounds()

    def cost(params):
        sim = wm.simulate_moisture(params, weather, et0, start, end, initial)
        return math.sqrt(mean((sim[d] - l4[d]) ** 2 for d in fit_days))

    runs = []
    for seed in seeds:
        result = differential_evolution(cost, bounds, seed=seed, maxiter=maxiter, popsize=popsize, tol=1e-6, polish=False)
        runs.append({"seed": seed, "calibration_rmse_m3_m3": round(float(result.fun), 5),
                     "parameters": dict(zip(wm.PARAMS, (round(float(x), 4) for x in result.x)))})
    best = min(runs, key=lambda r: r["calibration_rmse_m3_m3"])
    params = [best["parameters"][name] for name in wm.PARAMS]
    sim = wm.simulate_moisture(params, weather, et0, start, VALIDATION_PERIOD[1], initial)
    baseline = mean(l4[d] for d in fit_days)
    return {"model": "calibrated_daily_bucket_l4_v2",
            "target": "SMAP L4 SPL4SMGP.008 sm_rootzone, daily mean of 8 samples (m3/m3)",
            "climate": "NASA POWER demo point (PRECTOTCORR, T2M, T2M_MIN, T2M_MAX); ET0 by Hargreaves scaled to the station's Penman ET",
            "et0_scale": tables.constant("et0_scale"),
            "point": {"latitude": tables.constant("latitude"), "longitude": tables.constant("longitude")},
            "calibration": {"period": [d.isoformat() for d in CALIBRATION_PERIOD], **metrics(sim, l4, CALIBRATION_PERIOD)},
            "validation": {"period": [d.isoformat() for d in VALIDATION_PERIOD], **metrics(sim, l4, VALIDATION_PERIOD)},
            "constant_baseline_validation": {
                "description": "always predict the calibration-period mean; correlation is undefined",
                "rmse_m3_m3": round(math.sqrt(mean((baseline - l4[d]) ** 2 for d in days(*VALIDATION_PERIOD) if d in l4)), 4)},
            "parameters": best["parameters"], "chosen_seed": best["seed"], "seed_runs": runs,
            "search_bounds": dict(zip(wm.PARAMS, bounds)),
            "available_water_range_mm": [0, round(params[1], 1)],
            "inputs_sha256": {Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                              for p in (wm.POWER_CSV, l4_path, tables.site_file("station_daily.csv"))},
            "limitations": LIMITATIONS + ["different parameter sets fit SMAP L4 equally well (see seed_runs): the soil parameters are not identified by it"]}
