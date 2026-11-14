"""Bring datasets into the package data and keep the manifest (`data/datasets.csv`) honest.

`python -m xmart_analysis.datasets check` verifies every dataset against its manifest entry; `refresh` rewrites the derived columns;
`import-power SOURCE TARGET` trims a NASA POWER download and refuses gaps."""

import sys

import csv
import io
from datetime import date, timedelta
from pathlib import Path

from .engine import tables
from .engine.errors import EngineError

MODEL_COLUMNS = ("PRECTOTCORR", "T2M", "T2M_MIN", "T2M_MAX")
MISSING = -999.0


def _day(row):
    return date(int(row["YEAR"]), 1, 1) + timedelta(days=int(row["DOY"]) - 1)


def import_power(source_csv, target_csv):
    """Copy a POWER file keeping its header, trimming the trailing days the model columns do not have yet.

    A missing model value before the last valid day is an error: the climate record must be continuous.
    Returns (first day, last day, rows kept)."""
    header, body = Path(source_csv).read_text(encoding="utf-8").split("-END HEADER-")
    rows = list(csv.DictReader(io.StringIO(body.strip())))
    complete = [all(float(r[c]) != MISSING for c in MODEL_COLUMNS) for r in rows]
    if not any(complete):
        raise EngineError("empty_climate_file", "climate", "The POWER file has no day with all model columns")
    last = max(i for i, ok in enumerate(complete) if ok)
    gaps = [str(_day(r)) for r, ok in zip(rows[:last + 1], complete) if not ok]
    if gaps:
        raise EngineError("climate_gap", "climate", f"Missing model values before the last valid day: {gaps[:5]}", days=gaps)
    kept = rows[:last + 1]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(kept)
    Path(target_csv).write_text(header + "-END HEADER-\n" + out.getvalue(), encoding="utf-8")
    return _day(kept[0]), _day(kept[-1]), len(kept)


def refresh_manifest():
    """Rewrite the derived columns (rows, period, sha256) of `datasets.csv` from the files; the rest is kept."""
    rows = [dict(r) for r in tables.manifest()]
    for row in rows:
        row.update(tables.describe(row["path"]))
    with open(tables.DATA_DIR / "datasets.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    tables.read.cache_clear()
    return len(rows)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["check"]:
        problems = tables.check_sites() + tables.check_manifest()
        print("\n".join(problems) or "datasets and sites are consistent")
        return 1 if problems else 0
    if argv[:1] == ["refresh"]:
        print(f"{refresh_manifest()} manifest rows refreshed")
        return 0
    if argv[:1] == ["import-power"] and len(argv) == 3:
        first, last, rows = import_power(argv[1], argv[2])
        print(f"{rows} days kept, {first} to {last}")
        return 0
    print("usage: python -m xmart_analysis.datasets check | refresh | import-power SOURCE TARGET", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
