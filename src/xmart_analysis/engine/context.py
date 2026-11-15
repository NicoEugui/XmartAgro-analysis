"""Calibrated parameters and climate of a site, built once and reused across evaluations."""

import json

from . import tables
from . import water_model as wm


def build_context(site_id=None):
    """The soil the model was fitted with, the climate and the reference evapotranspiration of a site (the active one by default)."""
    site_id = site_id or tables.active_site()
    parameters = json.loads(tables.calibration_path(site_id).read_text(encoding="utf-8"))["parameters"]
    weather = wm.load_power(tables.site_file("power_daily.csv", site_id))
    return {"params": [parameters[k] for k in wm.PARAMS], "weather": weather,
            "et0": wm.precompute_et0(weather, tables.constants_of(site_id)["latitude"])}
