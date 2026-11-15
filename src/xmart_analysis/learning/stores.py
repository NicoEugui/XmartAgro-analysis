"""The stores of the architecture: where the daily series and the examples live, and the rule that governs them.

Both are tables of rows that are only ever added, never edited: a row whose key is already there is skipped, so loading the same data twice
changes nothing (the pipeline can be rerun for any period with no side effects) and new data (a producer's new season, a sensor's new
day) is simply appended. Rows are kept as JSON lines, one file per table. A database adapter replaces `AppendOnlyTable` without touching
anyone who uses a store. The registry (`registry.py`) and the results (`worker/adapters/files.py`) are the other two stores.

Series store (what the nightly pipeline reads):  `daily`  one row per field and day: NASA climate and the satellite's moisture;
                                                  `nodes`  one row per sensor node and day: raw and calibrated moisture.
Examples store (what the training reads):         `A`, `B` and `C`: one row per example of each model, with its answer.
"""

import json
from pathlib import Path


class AppendOnlyTable:
    """Rows kept as JSON lines in one file; a row with a key already stored is skipped."""

    def __init__(self, path, key):
        self.path, self.key = Path(path), tuple(key)

    def _key_of(self, row):
        return tuple(row[k] for k in self.key)

    def rows(self):
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def append(self, rows):
        """Add the rows whose key is new; returns (added, skipped)."""
        known, fresh, skipped = {self._key_of(r) for r in self.rows()}, [], 0
        for row in rows:
            key = self._key_of(row)
            if key in known:
                skipped += 1
                continue
            known.add(key)
            fresh.append(row)
        if fresh:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as stream:
                stream.writelines(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in fresh)
        return len(fresh), skipped

    def __len__(self):
        return len(self.rows())


class SeriesStore:
    """Daily climate and satellite per field, and readings per sensor node."""

    TABLES = {"daily": ("field_id", "date"), "nodes": ("node_id", "date")}

    def __init__(self, folder, table=AppendOnlyTable):
        self.tables = {name: table(Path(folder) / f"{name}.jsonl", key) for name, key in self.TABLES.items()}

    def append(self, name, rows):
        return self.tables[name].append(rows)

    def rows(self, name, field_id=None, first=None, last=None):
        """The rows of a table, of one field and between two ISO dates (both included) if given."""
        return [r for r in self.tables[name].rows()
                if (field_id is None or r["field_id"] == field_id) and (first is None or r["date"] >= first) and (last is None or r["date"] <= last)]


class ExamplesStore:
    """The examples of models A, B and C."""

    TABLES = {"B": ("field_id", "date"), "A": ("field_id", "producer_id", "season", "crop"), "C": ("field_id", "producer_id", "season", "crop")}

    def __init__(self, folder, table=AppendOnlyTable):
        self.tables = {name: table(Path(folder) / f"{name}.jsonl", key) for name, key in self.TABLES.items()}

    def append(self, model, rows):
        return self.tables[model].append(rows)

    def rows(self, model):
        return self.tables[model].rows()
