"""Does the water balance follow NASA SMAP soil moisture it was not calibrated on?

SMAP L4 root-zone moisture is the calibration target (a model product, 9 km); SMAP L3 retrievals are an independent
satellite observation of the surface layer. Both are read from the NASA CSV exports bundled in
sites/<site>/smap_l4.csv and smap_l3.csv (or from files given by path). Baseline: an antecedent precipitation index built from the same rain.
"""

import csv
from collections import defaultdict
from datetime import date, timedelta

from ..engine import context as engine_context
from ..engine import water_model as wm
from .files import check_point
from .stats import pearson, spearman

L4_COLUMN = "SPL4SMGP_008_Geophysical_Data_sm_rootzone"
L3_PREFIX = "SPL3SMP_E_006_Soil_Moisture_Retrieval_Data_"
L3_PAIRS = ((f"{L3_PREFIX}AM_soil_moisture", f"{L3_PREFIX}AM_retrieval_qual_flag"),
            (f"{L3_PREFIX}PM_soil_moisture_pm", f"{L3_PREFIX}PM_retrieval_qual_flag_pm"))
PERIODS = {"calibration": (date(2015, 4, 1), date(2020, 12, 31)), "validation": (date(2021, 1, 1), date(2026, 6, 30))}
API_DECAY = 0.85  # antecedent precipitation index: yesterday's index times this plus today's rain


def load_l4(path):
    """Daily mean root-zone moisture (m3/m3); a day needs all 8 samples."""
    check_point(path)
    samples = defaultdict(list)
    with open(path, newline="") as stream:
        for row in csv.DictReader(stream):
            value = float(row[L4_COLUMN])
            if 0 <= value <= 1:
                samples[date.fromisoformat(row["Date"][:10])].append(value)
    return {day: sum(v) / len(v) for day, v in samples.items() if len(v) == 8}


def load_l3(path):
    """Daily mean surface moisture of the retrievals flagged as recommended quality."""
    check_point(path)
    out = {}
    with open(path, newline="") as stream:
        for row in csv.DictReader(stream):
            values = [float(row[v]) for v, flag in L3_PAIRS if 0 < float(row[v]) < 1 and float(row[flag]) == 0]
            if values:
                out[date.fromisoformat(row["Date"][:10])] = sum(values) / len(values)
    return out


def antecedent_index(weather, last_day):
    out, index, day = {}, 0.0, min(weather)
    while day <= last_day:
        index = API_DECAY * index + weather[day]["PRECTOTCORR"]
        out[day] = index
        day += timedelta(days=1)
    return out


def anomalies(series, days):
    """Each value minus the mean of its 8-day-of-year bin."""
    bins = defaultdict(list)
    for d in days:
        bins[d.timetuple().tm_yday // 8].append(series[d])
    mean = {b: sum(v) / len(v) for b, v in bins.items()}
    return [series[d] - mean[d.timetuple().tm_yday // 8] for d in days]


def score(predictors, observed, days):
    target = [observed[d] for d in days]
    return {name: {"spearman": round(spearman([s[d] for d in days], target), 3),
                   "anomaly_r": round(pearson(anomalies(s, days), anomalies(observed, days)), 3)}
            for name, s in predictors.items()}


def run(l3_path, l4_path, context=None):
    context = context or engine_context.build_context()
    params, weather, et0 = context["params"], context["weather"], context["et0"]
    l4, l3 = load_l4(l4_path), load_l3(l3_path)
    start, end = PERIODS["calibration"][0], PERIODS["validation"][1]
    model = wm.simulate_moisture(params, weather, et0, start, end, l4[start])
    predictors = {"model": model, "smap_l4": l4, "rain_index": antecedent_index(weather, end)}
    periods = {}
    for name, (lo, hi) in PERIODS.items():
        days = [d for d in sorted(l3) if lo <= d <= hi and d in l4]
        periods[name] = {"days": len(days), "scores": score(predictors, l3, days)}
    return {"source": "smap_l3", "target": "SMAP L3 SPL3SMP-E.006 surface soil moisture", "periods": periods,
            "depth_note": "L3 senses the surface layer; the model represents the root zone, so the comparison is approximate"}
