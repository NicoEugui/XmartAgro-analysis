"""What XmartAgro would have said before each past season, and what that season turned out to be (a backtest).

For a field, a crop and a past season, the tool answers on the sowing day exactly as it would today: it takes the water the soil holds that day and applies the
climate of the **other** historical seasons to it (the season itself is left out, so the tool does not know its own future), counts how many ended with water, tight
or without it, and says the risk. Then the season itself is looked at with its real climate. Both come from the same model and the crop table, so this says whether the
tool's warning is consistent with what the season brought; it is **not** a check against what happened in a real field (nobody measured it): the one real check, the
unfavourable seasons the producers named, is put next to it. Fields, producers and outcomes are the simulated panel's.
"""

import copy
from functools import cache

from ..engine import crops_uy as cu
from ..engine import deficit, tables
from ..engine import water_scenarios as ws
from . import examples, outcomes, producers, season

CROPS = ("soybean_1st", "maize", "wheat", "barley")  # two summer and two winter crops
SURVEY_CROPS = ("soybean_1st", "maize")  # the crops the survey validator uses: the producers name summer droughts
FEATURED = ("soybean_1st", 2022)  # sown in November 2022: the 2022/23 drought
WARNED = ("medium", "high")  # risks that count as a warning


def case(field, context, crop, year, producer=None):
    """What the tool would have said for `crop` sown in `year` and what the season was (a dict), or None if the climate does not cover it."""
    params, weather, et0, spec = context["params"], context["weather"], context["et0"], cu.CROPS[crop]
    sowing = producers.sowing_date(crop, year, producer)
    water0 = season.water_at(params, sowing, weather, et0)
    if water0 is None:
        return None
    actual = season.stress(params, spec, crop, sowing, weather, et0, start_water_mm=water0)
    if actual is None:
        return None
    others = [s for y in tables.season_years() if y != year
              for s in [season.stress(params, spec, crop, producers.sowing_date(crop, y, producer), weather, et0, start_water_mm=water0)] if s is not None]
    counts = {c: sum(deficit.classify(s) == c for s in others) for c in deficit.CLASSES}
    worse_than = sum(s < actual for s in others) / len(others)
    drops = {deficit.DROP_NAMES[c]: n for c, n in deficit.split_in_10(counts, len(others)).items()}
    risk = deficit.water_risk(drops)
    actual_class = deficit.DROP_NAMES[deficit.classify(actual)]
    return {"field_id": field.field_id, "crop": crop, "season": ws.season_name(year), "sowing_date": str(sowing), "water_at_sowing_mm": round(water0, 1),
            "seasons_applied": len(others), "drops": drops, "risk": risk, "actual_stress": round(actual, 3), "actual_class": actual_class,
            "worse_than_share": round(worse_than, 3), "warned": risk in WARNED, "ended_out": actual_class == "out"}


def _share(part, whole):
    return round(part / whole, 3) if whole else None


def summary(rows):
    """How often the warning and the season agree, over the cases given."""
    out, high = [r for r in rows if r["ended_out"]], [r for r in rows if r["risk"] == "high"]
    return {"cases": len(rows), "ended_out": len(out), "warned_of_out": _share(sum(r["warned"] for r in out), len(out)),
            "high_risk_cases": len(high), "out_of_high_risk": _share(sum(r["ended_out"] for r in high), len(high)),
            "base_rate_out": _share(len(out), len(rows))}


def _survey_check(rows):
    """The real data: how many producers named a season unfavourable, against the mean stress of the panel's soybean and maize cases that season."""
    mentions = tables.survey_seasons()
    seasons = [ws.season_name(y) for y in ws.SEASON_YEARS[-5:]]

    def mean_stress(name, crop):
        values = [r["actual_stress"] for r in rows if r["season"] == name and r["crop"] == crop]
        return round(sum(values) / len(values), 3)
    return [{"season": s, "producers_naming_it": mentions.get(s, 0), **{f"{crop}_mean_stress": mean_stress(s, crop) for crop in SURVEY_CROPS}} for s in seasons]


def _run():
    panel = examples.Panel()
    national = [r for field in panel.fields for crop in CROPS for year in tables.season_years()
                if (r := case(field, panel.contexts[field.field_id], crop, year))]
    by_field = {f.field_id: f for f in panel.fields}
    own = []
    for producer in producers.all_producers():
        field = by_field[producer.field_id]
        for year, crop in producers.seasons(producer):
            if crop != producers.FALLOW and (r := case(field, panel.contexts[field.field_id], crop, year, producer)):
                own.append({**r, "producer_id": producer.producer_id,
                            "rating": outcomes.record(field, panel.contexts[field.field_id], crop, year, producer)["rating"]})
    crop, year = FEATURED
    featured = [r for r in national if r["crop"] == crop and r["season"] == ws.season_name(year)]
    return {"simulated": True, "crops": list(CROPS), "summary": summary(national), "by_crop": {c: summary([r for r in national if r["crop"] == c]) for c in CROPS},
            "featured": {"crop": crop, "season": ws.season_name(year), "rows": featured}, "producers": own, "producers_summary": summary(own),
            "survey_check": _survey_check(national)}


@cache
def _cached():
    return _run()


def run():
    """The backtest document (computed once per process)."""
    return copy.deepcopy(_cached())
