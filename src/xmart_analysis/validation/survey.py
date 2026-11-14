"""Are the seasons producers called unfavourable the ones the model finds driest?

Survey: `data/survey_unfavorable_seasons.csv` (what 12 producers wrote). Model: critical-stage stress of the crop sown on
its default date, with the same starting water every season so only the climate differs. The window is the last five
seasons, fixed before looking at the numbers (the survey asked about the last 3 to 5 years). Exploratory: self-reported,
few respondents, and the crop parameters are still pending a dataset.
"""

from ..engine import context as engine_context
from ..engine import crops_uy as cu
from ..engine import sowing_scenarios as sw
from ..engine import tables
from ..engine import water_scenarios as ws

CROPS = ("soybean_1st", "maize")
START_THETA = 0.28  # same for every season: only the climate differs
WINDOW_SEASONS = 5


def season_stress(crop, context):
    sowing = cu.CROPS[crop]["sowing"]
    doc = sw.evaluate_sowing(crop, sowing, START_THETA, sowing, context["params"], context["weather"], context["et0"])
    return {r["season"]: r["stress"] for r in doc["season_results"]}


def run(context=None):
    context = context or engine_context.build_context()
    mentions = tables.survey_seasons()
    seasons = [ws.season_name(y) for y in ws.SEASON_YEARS[-WINDOW_SEASONS:]]
    scenarios = ws.build_scenarios(**{k: context[k] for k in ("params", "weather", "et0")})
    entry = {"source": "producer_survey", "respondents": len({r["respondent"] for r in tables.read("survey/producer_survey")}),
             "answered": len({r["respondent"] for r in tables.read("survey/survey_unfavorable_seasons")}),
             "window": seasons, "mentions": {s: mentions.get(s, 0) for s in seasons},
             "lowest_water_seasons": scenarios["lowest_water_scenarios"][:3],
             "driest_by_rain_seasons": scenarios["driest_by_rain_scenarios"][:3], "crops": {}}
    most_named = sorted(seasons, key=lambda s: -mentions.get(s, 0))[:2]
    for crop in CROPS:
        stress = season_stress(crop, context)
        ranked = sorted(seasons, key=lambda s: -stress[s])
        entry["crops"][crop] = {"stress": {s: stress[s] for s in seasons}, "highest_stress": ranked[:2],
                                "most_named": most_named, "agree": set(ranked[:2]) == set(most_named)}
    return entry
