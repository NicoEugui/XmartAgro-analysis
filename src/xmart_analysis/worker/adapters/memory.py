"""In-memory implementations of the ports: tests, demos and local runs without a database."""

from datetime import timedelta

from ..domain import Job


class MemoryStore:
    def __init__(self):
        self.readings, self.inputs, self.results, self.jobs = [], {}, {}, []
        self._seq = 0

    def add_reading(self, reading):
        self.readings.append(reading)

    def request_job(self, field_id, now):
        self._seq += 1
        job = {"_id": f"job-{self._seq}", "field_id": field_id, "status": "pending", "requested_at": now,
               "claimed_at": None, "attempts": 0, "error": None}
        self.jobs.append(job)
        return job


class MemoryReadings:
    def __init__(self, store):
        self.store = store

    def latest(self, field_id):
        mine = [r for r in self.store.readings if r.field_id == field_id]
        return max(mine, key=lambda r: r.received_at) if mine else None


    def history(self, field_id, limit):
        """The last `limit` readings of the field, oldest first."""
        mine = sorted((r for r in self.store.readings if r.field_id == field_id), key=lambda r: r.received_at)
        return mine[-limit:]


class MemoryInputs:
    def __init__(self, store):
        self.store = store

    def get(self, field_id):
        return self.store.inputs.get(field_id)


class MemoryResults:
    def __init__(self, store):
        self.store = store

    def current_hash(self, field_id):
        return (self.store.results.get(field_id) or {}).get("inputs_hash")

    def save(self, field_id, document):
        self.store.results[field_id] = document


class MemoryJobQueue:
    def __init__(self, store, stale_after=timedelta(minutes=15)):
        self.store, self.stale_after = store, stale_after

    def claim(self, now):
        due = [j for j in self.store.jobs if j["status"] == "pending"
               or (j["status"] == "running" and now - j["claimed_at"] > self.stale_after)]
        if not due:
            return None
        doc = min(due, key=lambda j: j["requested_at"])
        doc.update(status="running", claimed_at=now, attempts=doc["attempts"] + 1)
        return Job(doc["_id"], doc["field_id"], doc["attempts"], doc["requested_at"], now)

    def _doc(self, job):
        return next(j for j in self.store.jobs if j["_id"] == job.id)

    def complete(self, job, now):
        self._doc(job).update(status="done", finished_at=now, error=None)
        for other in self.store.jobs:
            if other["status"] == "pending" and other["field_id"] == job.field_id and other["requested_at"] <= job.claimed_at:
                other.update(status="done", finished_at=now, error={"code": "superseded"})

    def release(self, job, error):
        self._doc(job).update(status="pending", error=error)

    def fail(self, job, error, now):
        self._doc(job).update(status="failed", finished_at=now, error=error)
