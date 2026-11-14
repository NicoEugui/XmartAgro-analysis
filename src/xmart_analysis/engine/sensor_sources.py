"""Sensor readings as the engine consumes them: simulated, typed by a person, or a stored reading from the API.

A stored reading is `{"sensor_id", "timestamp", "volumetric_moisture", "unit": "m3/m3", "depth_cm"?}`. It is flagged
`depth_unknown` without a depth, `stale_reading` when older than 24 h and `future_timestamp` when ahead of the clock.
Even then it is unvalidated: depth, calibration, quality and representativeness are still pending.
"""

from datetime import datetime, timedelta, timezone

from . import sensor_input as si
from . import tables
from .errors import EngineError

MAX_AGE = timedelta(hours=tables.constant("stale_reading_hours"))


class SimulatedSensor:
    def read(self):
        return {"source": si.SENSOR_SOURCE, "is_simulated": True, "volumetric_moisture": si.SIMULATED_THETA,
                "timestamp": None, "depth_cm": None, "sensor_id": None, "warnings": []}


class ManualSensor:
    """A value typed by a person: validated, but not a verified sensor measurement."""

    def __init__(self, moisture):
        self.moisture = moisture

    def read(self):
        return {"source": "manual_entry", "is_simulated": False, "volumetric_moisture": si.validate_theta(self.moisture),
                "timestamp": None, "depth_cm": None, "sensor_id": None, "warnings": ["manual_entry"]}


def parse_reading(payload, now, max_age=MAX_AGE):
    if not isinstance(payload, dict) or "volumetric_moisture" not in payload or "timestamp" not in payload:
        raise EngineError("sensor_payload_invalid", "sensor", "The sensor payload needs 'timestamp' and 'volumetric_moisture'")
    if payload.get("unit") != "m3/m3":
        raise EngineError("sensor_unit_unsupported", "sensor", f"Unsupported unit {payload.get('unit')!r}; expected 'm3/m3'",
                          received=payload.get("unit"))
    theta = si.validate_theta(payload["volumetric_moisture"])
    try:
        stamp = datetime.fromisoformat(str(payload["timestamp"]).replace("Z", "+00:00"))
    except ValueError:
        raise EngineError("sensor_payload_invalid", "sensor", f"Invalid timestamp {payload['timestamp']!r}") from None
    stamp = stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
    warnings = []
    if stamp > now + timedelta(minutes=5):
        warnings.append("future_timestamp")
    elif now - stamp > max_age:
        warnings.append("stale_reading")
    depth = payload.get("depth_cm")
    if not isinstance(depth, (int, float)) or isinstance(depth, bool) or depth <= 0:
        depth = None
        warnings.append("depth_unknown")
    return {"source": "backend_api_sensor", "is_simulated": False, "volumetric_moisture": theta,
            "timestamp": stamp.isoformat(), "depth_cm": depth, "sensor_id": payload.get("sensor_id"), "warnings": warnings}


def source_from_answers(sensor_answers):
    kind = (sensor_answers or {}).get("source", "simulated")
    if kind == "simulated":
        return SimulatedSensor()
    if kind == "manual":
        return ManualSensor(sensor_answers.get("moisture"))
    raise EngineError("unknown_sensor_source", "sensor.source", f"Unknown sensor source {kind!r}",
                      received=str(kind), known=["simulated", "manual"])
