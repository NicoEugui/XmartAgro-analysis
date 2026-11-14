"""A stored reading to the sensor description the engine validates and labels."""

from xmart_analysis.engine import sensor_input as si
from xmart_analysis.engine import sensor_sources as ss


def to_sensor_info(reading, now):
    if reading.sensor_type == "simulated":
        return {**ss.SimulatedSensor().read(), "volumetric_moisture": si.validate_theta(reading.moisture),
                "timestamp": reading.received_at.isoformat(), "sensor_id": reading.sensor_id}
    payload = {"sensor_id": reading.sensor_id, "timestamp": reading.received_at.isoformat(),
               "volumetric_moisture": reading.moisture, "unit": "m3/m3", "depth_cm": None}
    return ss.parse_reading(payload, now)
