"""Crop parameters for the rotation options model (demo point, Uruguay).

The values live in `data/crop_parameters.csv`, each row with its status and source (see `tables.provenance()`).
Until a dataset backs them they are `pending`, and no pending value may be presented as a measured fact. sowing = (month, day); stages = days of the initial, development, mid and late stages;
kc = (initial, mid, final); p = depletion fraction; counts_risk: whether the crop's own stress is reported.
"""

from datetime import date, timedelta

from . import tables
from .errors import EngineError

FALLOW_KC = tables.constant("fallow_kc")
CROPS = tables.crops()
UNSUPPORTED_CROPS = tables.unsupported_crops()  # crops the surveyed producers grow without a sourced calendar


def require_crop(crop):
    """Return the crop parameters or raise a structured error (instead of a bare KeyError)."""
    if crop in CROPS:
        return CROPS[crop]
    hint = " (no sourced sowing calendar yet)" if crop in UNSUPPORTED_CROPS else ""
    raise EngineError("unsupported_crop", "crop",
                      f"Unsupported crop '{crop}'{hint}. Supported crops: {', '.join(sorted(CROPS))}",
                      crop=str(crop), supported=sorted(CROPS), pending_sources=crop in UNSUPPORTED_CROPS)


def name_label_key(crop):
    return f"crops.{crop}.name"


def cycle_days(crop, spec=None):
    return sum((spec or CROPS[crop])["stages"])


def kc_on_day(crop, sowing, day, spec=None):
    """Crop coefficient on a date, or None if the crop does not occupy the soil that day. `spec` replaces the table's parameters
    (a producer's own variant of the crop)."""
    c = spec or CROPS[crop]
    if c.get("perennial"):
        return c["kc"][0] if day.month in (10, 11, 12, 1, 2, 3) else c["kc"][2]
    i = (day - sowing).days
    initial, development, mid, late = c["stages"]
    k_initial, k_mid, k_final = c["kc"]
    if i < 0 or i >= initial + development + mid + late:
        return None
    if i < initial:
        return k_initial
    i -= initial
    if i < development:
        return k_initial + (k_mid - k_initial) * (i + 1) / development
    i -= development
    if i < mid:
        return k_mid
    i -= mid
    return k_mid + (k_final - k_mid) * (i + 1) / late


def critical_window_from_sowing(crop, sowing, spec=None):
    """(start, end) of the critical stage for a crop sown on the given date: the mid stage."""
    c = spec or require_crop(crop)
    if c.get("perennial"):
        return date(sowing.year, 12, 1), date(sowing.year + 1, 3, 15)
    initial, development, mid, _ = c["stages"]
    return sowing + timedelta(days=initial + development), sowing + timedelta(days=initial + development + mid - 1)


def critical_window(crop, year):
    """(start, end) of the critical stage at the crop's default sowing date in `year`."""
    c = CROPS[crop]
    if c.get("perennial"):
        return date(year, 12, 1), date(year + 1, 3, 15)  # summer, the lotus peak-demand period
    return critical_window_from_sowing(crop, date(year, *c["sowing"]))
