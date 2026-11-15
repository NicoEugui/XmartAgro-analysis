"""Sensor readings as the engine consumes them: simulated, typed by a person, or a stored reading from the API.

A stored reading is `{"sensor_id", "timestamp", "volumetric_moisture", "unit": "m3/m3", "depth_cm"?}`. It is flagged
`depth_unknown` without a depth, `stale_reading` when older than 24 h and `future_timestamp` when ahead of the clock.
Even then it is unvalidated: depth, calibration, quality and representativeness are still pending.
"""

from datetime import date, datetime, timedelta, timezone

from . import sensor_input as si
from . import sensor_series, tables
from . import water_model as wm
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


def apply_history(info, context):
    """The state the scenarios start from when the readings of the last days are known: the model's water corrected by the series.

    `info` is a reading description that may carry `history` ([{date, moisture}], oldest first). Without it, or when the climate
    does not cover the series, the reading is used as it is (the second case adds the warning `series_beyond_climate`).
    With it, `volumetric_moisture` becomes the corrected state on the last day, `raw_moisture` keeps the last reading and
    `series` records how the state was reached, day by day."""
    history = info.get("history")
    if not history:
        return info
    readings = {date.fromisoformat(h["date"]): h["moisture"] for h in history}
    first, last = min(readings), max(readings)
    if not wm.has_all_days(context["weather"], first, last):
        return {**info, "warnings": [*info["warnings"], "series_beyond_climate"]}
    gain = tables.constant("sensor_gain")
    modeled = sensor_series.assimilate(context, readings, gain)
    return {**info, "raw_moisture": readings[last], "volumetric_moisture": modeled[last],
            "series": {"method": "state_correction", "gain": gain, "days": len(readings), "period": [first.isoformat(), last.isoformat()],
                       "history": [{"date": d.isoformat(), "reading": readings[d], "modeled": round(modeled[d], 4)} for d in sorted(readings)]}}


def source_from_answers(sensor_answers):
    kind = (sensor_answers or {}).get("source", "simulated")
    if kind == "simulated":
        return SimulatedSensor()
    if kind == "manual":
        return ManualSensor(sensor_answers.get("moisture"))
    raise EngineError("unknown_sensor_source", "sensor.source", f"Unknown sensor source {kind!r}",
                      received=str(kind), known=["simulated", "manual"])
