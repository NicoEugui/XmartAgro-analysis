from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Reading:
    field_id: str
    sensor_id: str
    moisture: float
    sensor_type: str
    received_at: datetime


@dataclass(frozen=True)
class Job:
    id: str
    field_id: str
    attempts: int
    requested_at: datetime
    claimed_at: datetime


@dataclass(frozen=True)
class Outcome:
    status: str  # "computed" or "unchanged"
    inputs_hash: str
    notes: tuple = ()
