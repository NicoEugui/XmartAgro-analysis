"""Deficit classes of a season: how much of the crop's demand was left unmet in its critical stage."""

from . import tables

THRESHOLDS = (tables.constant("deficit_threshold_low"), tables.constant("deficit_threshold_high"))
CLASSES = ("low_deficit", "moderate_deficit", "high_deficit")
DROP_NAMES = {"low_deficit": "ok", "moderate_deficit": "tight", "high_deficit": "out"}  # the API and panel vocabulary


def classify(stress, thresholds=THRESHOLDS):
    if stress < thresholds[0]:
        return "low_deficit"
    return "moderate_deficit" if stress < thresholds[1] else "high_deficit"


def split_in_10(counts, n):
    """Split counts into 10 parts by largest remainder; each part is about n/10 cases (not a probability)."""
    quotas = {c: counts[c] * 10 / n for c in CLASSES}
    base = {c: int(quotas[c]) for c in CLASSES}
    for c in sorted(CLASSES, key=lambda c: quotas[c] - base[c], reverse=True)[:10 - sum(base.values())]:
        base[c] += 1
    return {c: base[c] for c in CLASSES}


def water_risk(drops):
    """low, medium or high from the number of high-deficit drops (provisional thresholds in `model_constants.csv`); None without drops."""
    if not drops:
        return None
    out = drops["out"]
    if out <= tables.constant("water_risk_low_max_out"):
        return "low"
    return "medium" if out <= tables.constant("water_risk_medium_max_out") else "high"
