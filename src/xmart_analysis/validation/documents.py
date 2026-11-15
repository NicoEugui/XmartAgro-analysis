"""Every validation document of a run in one place: what `validate`, `report` and the frontend charts are drawn from."""

from ..engine import tables
from . import imerg, ndvi, rain_sensitivity, sensor_assimilation, smap, survey

BUNDLED = {"smap_l3": "smap_l3.csv", "smap_l4": "smap_l4.csv", "modis_ndvi": "modis_ndvi.csv", "imerg": "imerg_daily.csv"}


def build(context, smap_l3=None, smap_l4=None, modis_ndvi=None, imerg_file=None):
    """The documents of the validators whose files are given; the producer survey and the simulated-sensor experiments always run."""
    doc = {"survey": survey.run(context), "sensor": sensor_assimilation.run(context),
           "sensor_windows": sensor_assimilation.windows(context), "sensor_recalibration": sensor_assimilation.recalibrate(context)}
    if smap_l3:
        doc["smap"] = smap.run(smap_l3, smap_l4, context)
    if modis_ndvi:
        doc["ndvi"] = ndvi.run(modis_ndvi, context)
    if imerg_file:
        doc["imerg"] = imerg.run(imerg_file, context)
        doc["rain_sensitivity"] = rain_sensitivity.run(imerg_file, context)
        doc["rain_decision"] = {"imerg": doc["imerg"], "sensitivity": doc["rain_sensitivity"]}
    return doc


def bundled(context):
    """The same, with the NASA files shipped in the site folder (a validator whose file the site lacks is left out)."""
    paths = {name: tables.site_file(file) for name, file in BUNDLED.items()}
    have = {name: path for name, path in paths.items() if path.exists()}
    both = "smap_l3" in have and "smap_l4" in have
    return build(context, have.get("smap_l3") if both else None, have.get("smap_l4") if both else None, have.get("modis_ndvi"), have.get("imerg"))
