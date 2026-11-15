"""Soil health of each producer's field from the rotation they wrote in the form and the field's soil analysis.

The rotation is the survey's (written order, years assigned by the simulation, see `producers`); the soil analysis is the simulated one
of `soil_plans`. The rules are those of `engine.soil_health`; this only feeds them.
"""

from ..engine import soil_health as rules
from ..engine import water_scenarios as ws
from . import producers, soil_plans


def producer_table():
    """One row per producer: the crops of their last seasons, the state, trend and precision of their soil, and what their rotation does to it."""
    rows = []
    for producer in producers.all_producers():
        history = producers.seasons(producer, full=True)
        crops = [crop for _, crop in history]
        plan = soil_plans.of_field(producer.field_id)
        analysis = {"organic_matter_pct": plan.organic_matter_pct, "erosion_t_ha_yr": plan.erosion_t_ha_yr}
        rows.append({"producer_id": producer.producer_id, "field_id": producer.field_id,
                     "season_names": [ws.season_name(year) for year, _ in history], "crops": crops,
                     **rules.assess(crops, analysis), "rotation_effect": rules.effect(producers.crop_sequence(producer.respondent, True))["effect"],
                     "simulated": True, "soil_analysis_status": plan.status})
    return rows
