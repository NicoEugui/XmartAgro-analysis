"""NDVI curves of a season and the five numbers that summarize one (the input of model C).

The real MODIS curve of the Soriano point and a simulated curve of any crop (or of fallow) are summarized by the same `summary`,
so model C does not care where a curve came from. A simulated curve rises as the crop grows, stays high through the mid stage,
falls in the late stage and loses part of its peak where the crop was short of water; noise and cloud residue are added.
"""

import random
from datetime import date, timedelta

from ..engine import crops_uy as cu
from ..engine import tables

FIRST_MONTH_DAY = (4, 1)  # a season's curve runs from 1 April to the next 31 March
COMPOSITE_DAYS = 16
COMPOSITES = 23
FEATURES = ("start_offset", "peak_offset", "peak_value", "duration_days", "peaks")


def _shape(i, stages):
    """0 to 1 share of the peak greenness `i` days after sowing."""
    initial, development, mid, late = stages
    if i < 0 or i >= sum(stages):
        return 0.0
    if i < initial:
        return 0.05
    i -= initial
    if i < development:
        return 0.05 + 0.95 * i / development
    i -= development
    return 1.0 if i < mid else 1.0 - 0.7 * (i - mid) / late


def curve(year, crop, sowing, spec, stress, peak, rng):
    """[(days from 1 April, NDVI)] of the season: bare soil with a small weed bump if `crop` is None."""
    bare, sd = tables.constant("learn_ndvi_bare"), tables.constant("learn_ndvi_noise_sd")
    start = date(year, *FIRST_MONTH_DAY)
    out = []
    for k in range(COMPOSITES):
        offset = k * COMPOSITE_DAYS
        i = (start + timedelta(days=offset) - sowing).days if crop else -1
        green = peak * (1 - tables.constant("learn_ndvi_stress_loss") * stress) if crop else bare + 0.05
        value = bare + (green - bare) * _shape(i, spec["stages"]) if crop else bare + 0.05 * rng.random()
        if rng.random() < tables.constant("learn_ndvi_cloud_share"):
            value -= 0.15
        out.append((offset, round(min(0.95, max(0.0, value + rng.gauss(0, sd))), 3)))
    return out


def summary(series):
    """The five numbers of a curve ([(days from 1 April, NDVI)]): start of green, day and height of the peak, days green, peaks."""
    cut = tables.constant("learn_ndvi_bare") + tables.constant("learn_ndvi_good_cut")
    green = [d for d, v in series if v > cut]
    values = [v for _, v in series]
    peaks = sum(values[i] > cut and values[i] > values[i - 1] and values[i] >= values[i + 1] for i in range(1, len(values) - 1))
    top = max(series, key=lambda p: p[1])
    return {"start_offset": green[0] if green else -1, "peak_offset": top[0], "peak_value": top[1],
            "duration_days": len(green) * COMPOSITE_DAYS, "peaks": peaks}


def from_composites(composites, year):
    """[(days from 1 April, NDVI)] of the season starting in `year` from [(date, NDVI)] composites (the real MODIS series)."""
    start, end = date(year, *FIRST_MONTH_DAY), date(year + 1, 3, 31)
    return [((d - start).days, v) for d, v in composites if start <= d <= end]
