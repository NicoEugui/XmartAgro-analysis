"""The soil analysis and Soil Use Plan of each field of the panel (organic matter, phosphorus, pH, estimated erosion) and the soil unit it sits on.

No real analysis exists for these fields, so the numbers are simulated and say so (`status: simulated`): they follow the texture, capacity and slope
of the field (heavier soils hold more organic matter and phosphorus, steeper fields lose more soil) and stay inside the ranges the contract accepts.
The soil type and its code are not simulated: they are the field's soil unit (CONEAT in Uruguay) from the soil-map module (`soils`).
"""

from dataclasses import dataclass

from ..engine import tables
from . import fields


@dataclass(frozen=True)
class SoilPlan:
    field_id: str
    analysis_date: str
    organic_matter_pct: float
    phosphorus_bray_ppm: float
    ph: float
    erosion_t_ha_yr: float
    soil_type: str  # the unit's dominant soil orders, e.g. "Vertisol; Brunosol"; empty without a soil system
    coneat: str  # the unit's code when the system is CONEAT, empty otherwise
    status: str  # of the analysis numbers


def all_plans():
    units = {f.field_id: f.soil_unit for f in fields.all_fields()}
    out = []
    for r in tables.read("learning/soil_plans"):
        unit = units[r["field_id"]]
        out.append(SoilPlan(r["field_id"], r["analysis_date"], float(r["organic_matter_pct"]), float(r["phosphorus_bray_ppm"]), float(r["ph"]),
                            float(r["erosion_t_ha_yr"]), "; ".join(unit.dominant_orders) if unit else "",
                            unit.code if unit and unit.system == "coneat" else "", r["status"]))
    return tuple(out)


def of_field(field_id):
    return next(p for p in all_plans() if p.field_id == field_id)
