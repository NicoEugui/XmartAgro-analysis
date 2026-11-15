"""Current soil moisture input.

Source of truth for "how much water does the soil have today": the physical ESP32 sensors in the
field. Until they are installed the reading is simulated and says so. Satellite products are context at most, never a substitute for local measurements.

A sensor measures volumetric moisture (m3/m3), not available water in mm. The conversion needs field
capacity, wilting point and the depth the sensors represent; until those are known `available_water_mm`
stays None and any millimetre figure used inside the model is labelled as an assumption.
"""

import math

from . import water_model as wm
from . import tables
from .errors import EngineError
from .i18n import label

SIMULATED_THETA = tables.constant("simulated_theta")  # illustrative value, NOT a field measurement
SENSOR_SOURCE = "simulated_iot_sensor"
CORRECTED_SOURCE = "smap_corrected"  # the satellite as model B corrects it, standing in for a sensor


MAX_THETA = tables.constant("max_theta")  # beyond any soil porosity: a sensor fault, not moisture


def validate_theta(theta):
    """Return the reading as float or raise EngineError for a missing, non-numeric, NaN or impossible value."""
    if theta is None or isinstance(theta, bool) or not isinstance(theta, (int, float)):
        raise EngineError("invalid_moisture", "volumetric_moisture",
                          f"Soil moisture must be a number in m3/m3, got {theta!r}", received=repr(theta))
    if math.isnan(theta) or math.isinf(theta):
        raise EngineError("invalid_moisture", "volumetric_moisture", "Soil moisture must be a finite number",
                          received=repr(theta))
    if not 0.0 <= theta <= MAX_THETA:
        raise EngineError("moisture_out_of_range", "volumetric_moisture",
                          f"Soil moisture {theta} m3/m3 is outside the physically possible range 0 to {MAX_THETA}",
                          received=theta, minimum=0.0, maximum=MAX_THETA)
    return float(theta)


def reading_warnings(theta, params):
    """Warnings (codes with labels) when a valid reading falls outside the assumed soil bounds."""
    warnings = []
    if theta < params[0]:
        warnings.append({"code": "below_assumed_wilting_point", "label": label("sensor.warning.below_wilting")})
    if theta > params[0] + params[1] / wm.ROOT_DEPTH_MM:
        warnings.append({"code": "above_assumed_field_capacity", "label": label("sensor.warning.above_capacity")})
    return warnings


def reading(theta=SIMULATED_THETA, source_info=None):
    """The current reading, in the structure a real ESP32 reading will have.

    source_info (from sensor_sources) describes where the value comes from; without it the reading is the
    simulated one."""
    info = source_info or {"source": SENSOR_SOURCE, "is_simulated": True}
    return {"source": info["source"], "is_simulated": info["is_simulated"], "volumetric_moisture": theta,
            "unit": "m3/m3", "available_water_mm": None, "calibration_status": "pending"}


def soil_water_block(theta=SIMULATED_THETA, source_info=None):
    block = reading(theta, source_info)
    info = source_info or {}
    block["available_water_status"] = "not_determined"
    block["reading_date"] = info.get("timestamp")  # a real reading carries its timestamp
    block["reading_validation"] = {"depth_cm": info.get("depth_cm"), "calibration": "pending",
                                   "quality_checks": "pending", "spatial_representativeness": "pending"}
    block["source_warnings"] = list(info.get("warnings", []))
    block["raw_moisture"] = info.get("raw_moisture")  # the last reading, when the state shown is the model's corrected by a series
    block["series"] = info.get("series")
    block["model_b"] = info.get("model_b")  # set when model B's corrected satellite stands in for the sensor
    block["requirements_before_real_sensors"] = {
        "note": label("soil_water.requirements.note"),
        "items": [label("soil_water.requirements.depth"), label("soil_water.requirements.calibration"),
                  label("soil_water.requirements.quality"), label("soil_water.requirements.representativeness")]}
    if info.get("source") == "manual_entry":
        block["note"] = label("soil_water.note_manual")
    elif info and not info.get("is_simulated", True):
        block["note"] = label("soil_water.note_real")
    else:
        block["note"] = label("soil_water.note")
    block["conversion_note"] = label("soil_water.conversion_note")
    return block


def to_available_water_mm(theta, params):
    """Convert volumetric moisture to mm using ASSUMED bucket soil parameters (theta_min, capacity)."""
    return wm.water_from_theta(theta, params[0], params[1])

