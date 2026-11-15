"""Soil health from what a field grew: state, trend and precision, by rules (no learning).

Each season scores what its crop does to the soil: the stubble it leaves, a cover crop or pasture, and the months the soil stays bare.
Soybean after soybean costs score; a soil analysis (organic matter, estimated erosion) moves it, and without one the precision is low.
All thresholds are provisional assumptions in `model_constants.csv` and `crop_soil_effects.csv`; this says how a rotation treats the
soil, not how much soil is lost. `bare_months` can come from the NASA NDVI curve when the crop of each season is known; until
then it is read from the crop's cycle. One crop per season: a winter crop and the soybean sown after it count as two seasons."""

from . import crops_uy as cu
from . import tables

SOYBEANS = ("soybean_1st", "soybean_2nd")
DAYS_PER_MONTH = 30.4


def bare_months(crop):
    """Months of the year the soil is bare under this crop: none under a cover or pasture, the rest of the year after a crop's cycle."""
    if crop == "fallow":
        return 12.0
    if tables.soil_effects()[crop]["cover"]:
        return 0.0
    cycle = cu.cycle_days(crop) if crop in cu.CROPS else tables.constant("soil_unmodelled_cycle_days")
    return max(0.0, 12 - cycle / DAYS_PER_MONTH)


def season_score(crop, bare=None):
    effect = tables.soil_effects()[crop]
    bare = bare_months(crop) if bare is None else bare
    score = effect["residue"] - tables.constant("soil_bare_month_penalty") * max(0.0, bare - tables.constant("soil_bare_months_ok"))
    return score + (tables.constant("soil_cover_bonus") if effect["cover"] else 0.0)


def soybean_streak(crops):
    """Consecutive soybean seasons at the end of the sequence."""
    streak = 0
    for crop in reversed(crops):
        if crop not in SOYBEANS:
            break
        streak += 1
    return streak


def _state(score):
    return "good" if score >= tables.constant("soil_good_score") else "regular" if score >= tables.constant("soil_poor_score") else "poor"


def _trend(scores):
    if len(scores) < tables.constant("soil_min_seasons_trend"):
        return "unknown"
    half = len(scores) // 2
    change = sum(scores[-half:]) / half - sum(scores[:half]) / half
    delta = tables.constant("soil_trend_delta")
    return "improving" if change >= delta else "worsening" if change <= -delta else "stable"


def _analysis_adjust(plan):
    """(score moved by the soil analysis, what moved it): a steep erosion or a low organic matter costs, a high organic matter gains."""
    if plan is None:
        return 0.0, []
    moved, why = 0.0, []
    tolerance, adjust = tables.constant("soil_erosion_tolerance"), tables.constant("soil_analysis_adjust")
    if plan["erosion_t_ha_yr"] > tolerance:
        moved -= min(1.0, plan["erosion_t_ha_yr"] / tolerance - 1) + adjust
        why.append("erosion_above_tolerance")
    if plan["organic_matter_pct"] < tables.constant("soil_organic_low"):
        moved -= adjust
        why.append("low_organic_matter")
    elif plan["organic_matter_pct"] >= tables.constant("soil_organic_high"):
        moved += adjust
        why.append("high_organic_matter")
    return moved, why


def assess(crops, plan=None):
    """State, trend and precision of a soil from its seasons' crops (oldest first); `plan` is the soil analysis {organic_matter_pct,
    erosion_t_ha_yr} or None."""
    scores = [season_score(c) for c in crops]
    streak = soybean_streak(crops)
    penalty = min(tables.constant("soil_soy_streak_cap"), tables.constant("soil_soy_streak_penalty") * max(0, streak - 1))
    moved, why = _analysis_adjust(plan)
    score = sum(scores) / len(scores) - penalty + moved
    return {"state": _state(score), "trend": _trend(scores), "precision": "medium" if plan else "low", "score": round(score, 2),
            "seasons": len(crops), "soybean_streak": streak, "bare_months_per_year": round(sum(map(bare_months, crops)) / len(crops), 1),
            "legume_or_pasture_seasons": sum(tables.soil_effects()[c]["legume"] and c not in SOYBEANS or tables.soil_effects()[c]["cover"] for c in crops),
            "soybean_streak_penalty": round(penalty, 2), "analysis_adjust": round(moved, 2), "analysis_reasons": why}


def effect(rotation):
    """What a rotation (crops in order, repeated) does to the soil: improves, maintains or worsens. It needs no analysis."""
    cycle = list(rotation)
    score = sum(season_score(c) for c in cycle) / len(cycle)
    streak = max((soybean_streak(cycle[:i + 1]) for i in range(len(cycle))), default=0)
    score -= min(tables.constant("soil_soy_streak_cap"), tables.constant("soil_soy_streak_penalty") * max(0, streak - 1))
    return {"effect": {"good": "improves", "regular": "maintains", "poor": "worsens"}[_state(score)], "score": round(score, 2)}
