"""A stored reading to the sensor description the engine validates and labels."""

from xmart_analysis.engine import sensor_input as si
from xmart_analysis.engine import sensor_sources as ss


def daily_history(readings):
    """One validated reading per day (the day's last), oldest first, as the engine takes them."""
    last = {}
    for r in sorted(readings, key=lambda r: r.received_at):
        last[r.received_at.date()] = si.validate_theta(r.moisture)
    return [{"date": day.isoformat(), "moisture": theta} for day, theta in last.items()]


def to_sensor_info(reading, now, history=()):
    """The latest reading as the engine describes a sensor; with the readings of the last days (more than one day) it also carries them."""
    if reading.sensor_type == "simulated":
        info = {**ss.SimulatedSensor().read(), "volumetric_moisture": si.validate_theta(reading.moisture),
                "timestamp": reading.received_at.isoformat(), "sensor_id": reading.sensor_id}
    else:
        payload = {"sensor_id": reading.sensor_id, "timestamp": reading.received_at.isoformat(),
                   "volumetric_moisture": reading.moisture, "unit": "m3/m3", "depth_cm": None}
        info = ss.parse_reading(payload, now)
    days = daily_history(history)
    return {**info, "history": days} if len(days) > 1 else info
