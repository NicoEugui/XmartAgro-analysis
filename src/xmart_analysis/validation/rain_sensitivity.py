"""How much do the results depend on the rain source? Run the model with NASA POWER rain and with NASA GPM IMERG rain.

Only the daily rain changes: temperature, evaporative demand and the soil parameters (fitted with POWER rain) stay the same, so the
difference is the effect of swapping the rain alone. Both runs use the seasons that lie inside the IMERG record, so they are compared on
the same seasons. Exploratory: it measures sensitivity, it does not say which source is right.
"""

from ..engine import context as engine_context
from ..engine import deficit, rotations, tables
from . import imerg, survey
from .stats import spearman


def restricted_context(context, rain_by_day, source):
    """The context on the days IMERG covers, with the rain of `source` (`power` keeps POWER's, `imerg` uses IMERG's)."""
    weather = {d: {**w, "PRECTOTCORR": rain_by_day[d] if source == "imerg" else w["PRECTOTCORR"]}
               for d, w in context["weather"].items() if d in rain_by_day}
    return {"params": context["params"], "weather": weather, "et0": {d: context["et0"][d] for d in weather}}


def _kw(ctx):
    return {k: ctx[k] for k in ("params", "weather", "et0")}


def run(path, context=None):
    context = context or engine_context.build_context()
    rain = imerg.load(path)
    ctx = {source: restricted_context(context, rain, source) for source in ("power", "imerg")}
    high = deficit.THRESHOLDS[1]
    crops = {}
    for crop in survey.CROPS:
        stress = {source: survey.season_stress(crop, ctx[source]) for source in ctx}
        seasons = sorted(set(stress["power"]) & set(stress["imerg"]))
        p, i = [stress["power"][s] for s in seasons], [stress["imerg"][s] for s in seasons]
        crops[crop] = {"seasons": len(seasons), "spearman_between_sources": round(spearman(p, i), 3),
                       "mean_abs_difference": round(sum(abs(a - b) for a, b in zip(p, i)) / len(p), 3),
                       "high_deficit_seasons": {"power": sum(v >= high for v in p), "imerg": sum(v >= high for v in i)},
                       "stress": [{"season": s, "power": stress["power"][s], "imerg": stress["imerg"][s]} for s in seasons]}
    shares = {}
    for rid in rotations.ids():
        result = {source: rotations.evaluate(rid, _kw(ctx[source])) for source in ctx}
        shares[rid] = {source: round(r["season_counts"]["high_deficit"] / r["combinations"], 3) for source, r in result.items()}
    named = tables.survey_seasons()
    first = crops[survey.CROPS[0]]["stress"]
    producers = [{"season": r["season"], "mentions": named[r["season"]], "power": r["power"], "imerg": r["imerg"]}
                 for r in first if r["season"] in named]
    return {"source": "gpm_imerg", "crops": crops, "rotations_high_deficit_share": shares,
            "producer_seasons": producers, "first_crop": survey.CROPS[0],
            "note": "only the rain changes; the soil parameters were fitted with POWER rain, so this is a sensitivity, not a recalibration"}
