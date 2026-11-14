from datetime import datetime
from typing import Protocol

from .domain import Job, Reading


class ReadingsRepository(Protocol):
    def latest(self, field_id: str) -> Reading | None: ...


class InputsRepository(Protocol):
    def get(self, field_id: str) -> dict | None: ...


class ResultsRepository(Protocol):
    def current_hash(self, field_id: str) -> str | None: ...
    def save(self, field_id: str, document: dict) -> None: ...


class JobQueue(Protocol):
    def claim(self, now: datetime) -> Job | None: ...
    def complete(self, job: Job, now: datetime) -> None: ...
    def release(self, job: Job, error: dict) -> None: ...
    def fail(self, job: Job, error: dict, now: datetime) -> None: ...


class Analyzer(Protocol):
    version: str

    def analyze(self, answers: dict, sensor_info: dict) -> dict: ...
