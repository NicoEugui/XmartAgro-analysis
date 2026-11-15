"""The fields of the panel: two real (Soriano and La Estanzuela: NASA climate, SMAP, MODIS and a fitted soil) and six simulated.

Every field has its own NASA POWER record at its own coordinate. A simulated field has nothing else from NASA: its soil is the model's
soil times a capacity factor and a wilting shift (the model does not know it, exactly as in the sensor experiment), and the satellite
sees that soil through a planted error (`smap_offset`, `smap_scale`) that model B must recover. The soil's texture, its capacity and that error
come from the field's soil unit (CONEAT in Uruguay, see `soils`), so a better soil map changes the panel and nothing else.
"""

import math
import random
from dataclasses import dataclass

from ..engine import context as engine_context
from ..engine import sensor_series, tables
from ..engine import water_model as wm
from ..soils import derive, units as soil_units
from ..soils.ports import SoilUnit
from ..validation import smap as smap_files


@dataclass(frozen=True)
class Field:
    field_id: str
    name: str
    department: str
    site_id: str  # the site holding the field's NASA POWER record (and, for a real field, its SMAP, MODIS and fitted soil)
    latitude: float
    longitude: float
    real: bool
    capacity_factor: float  # the real soil's water capacity against the model's: derived from the soil unit unless the table states it
    theta_min_shift: float
    clay: int  # texture class (0 light, 1 medium, 2 heavy) derived from the soil unit; the name is kept for the models' features
    slope_pct: float
    smap_offset: float | None  # the planted satellite error of a simulated field, by texture class
    smap_scale: float | None
    soil_unit: SoilUnit | None  # the CONEAT (or other system's) unit of the coordinate, None without a soil system


def all_fields():
    units = soil_units.load()
    out = []
    for r in tables.read("learning/fields"):
        unit, real = units.get(r["field_id"]), r["kind"] == "real"
        texture = derive.texture_class(unit)
        offset, scale = (None, None) if real else derive.satellite_error(texture, r["field_id"])
        out.append(Field(r["field_id"], r["name"], r["department"], r["site_id"], float(r["latitude"]), float(r["longitude"]), real,
                         float(r["capacity_factor"]) if r["capacity_factor"] else derive.capacity_factor(unit), float(r["theta_min_shift"]),
                         texture, float(r["slope_pct"]), offset, scale, unit))
    return tuple(out)


def get(field_id):
    return next(f for f in all_fields() if f.field_id == field_id)


def real_sites():
    """The sites of the fields that have a real satellite record and a fitted soil."""
    return sorted(f.site_id for f in all_fields() if f.real)


def _distance(field, site_id):
    constants = tables.constants_of(site_id)
    return math.hypot(field.latitude - constants["latitude"], field.longitude - constants["longitude"])


def build_context(field, sites=None):
    """What the pipeline knows about the field: its own NASA climate and a soil (the nearest fitted site's: it does not know the field's).

    `sites` is {site id: context} of the fitted sites; a real field is its site's context as is, a simulated one has its own POWER
    record at its own point, with the ET0 of its latitude."""
    sites = sites or {site: engine_context.build_context(site) for site in real_sites()}
    if field.real:
        return sites[field.site_id]
    weather = wm.load_power(tables.site_file("power_daily.csv", field.site_id))
    nearest = min(sites, key=lambda s: _distance(field, s))
    return {"params": sites[nearest]["params"], "weather": weather, "et0": wm.precompute_et0(weather, field.latitude)}


def soil(field, params):
    """The field's real soil, which the model does not know."""
    return sensor_series.truth_params(params, field.capacity_factor, field.theta_min_shift)


def truth(field, context, window):
    """{date: moisture} of the field's real soil over `window`."""
    return wm.simulate_moisture(soil(field, context["params"]), context["weather"], context["et0"], *window,
                                tables.constant("sensor_truth_start_theta"))


def smap(field, context, window):
    """{date: root-zone moisture} the satellite reports: the real SMAP L4 at the real point, a planted error on the truth elsewhere."""
    if field.real:
        first, last = window
        return {d: v for d, v in smap_files.load_l4(tables.site_file("smap_l4.csv", field.site_id), field.site_id).items() if first <= d <= last}
    noise = random.Random(f"{tables.constant('learn_seed')}:smap:{field.field_id}")
    sd = tables.constant("learn_smap_noise_sd")
    return {d: round(field.smap_offset + field.smap_scale * t + noise.gauss(0, sd), 4) for d, t in sorted(truth(field, context, window).items())}
