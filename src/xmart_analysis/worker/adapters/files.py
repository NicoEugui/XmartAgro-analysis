"""File-based adapters: run the analysis without any database and keep the results as JSON files."""

import json
from datetime import datetime
from pathlib import Path

from ..domain import Reading
from .memory import MemoryStore


def load_scenario(path):
    """A scenario file `{field_id, readings: [...], inputs: {farmer, agronomist}}` as a populated in-memory store."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    store = MemoryStore()
    field_id = data["field_id"]
    for r in data["readings"]:
        store.add_reading(Reading(field_id, r["sensor_id"], r["moisture"], r["sensor_type"],
                                  datetime.fromisoformat(r["received_at"].replace("Z", "+00:00"))))
    store.inputs[field_id] = data.get("inputs")
    return field_id, store


class FileResults:
    """ResultsRepository writing `<directory>/<field_id>.results.json`."""

    def __init__(self, directory):
        self.directory = Path(directory)

    def path(self, field_id):
        return self.directory / f"{field_id}.results.json"

    def current_hash(self, field_id):
        try:
            return json.loads(self.path(field_id).read_text(encoding="utf-8")).get("inputs_hash")
        except FileNotFoundError:
            return None

    def save(self, field_id, document):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path(field_id).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def load(self, field_id):
        return json.loads(self.path(field_id).read_text(encoding="utf-8"))
