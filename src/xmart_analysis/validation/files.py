"""Guard for NASA exports: a file downloaded for one point must not be validated against another site."""

import csv

from ..engine import tables
from ..engine.errors import EngineError

TOLERANCE_DEGREES = 0.05


def check_point(path):
    """Raise if the file states a Latitude/Longitude that is not the active site's point (files without them pass)."""
    with open(path, newline="") as stream:
        row = next(csv.DictReader(stream), None)
    if not row or "Latitude" not in row or "Longitude" not in row:
        return
    here = (tables.constant("latitude"), tables.constant("longitude"))
    there = (float(row["Latitude"]), float(row["Longitude"]))
    if abs(there[0] - here[0]) > TOLERANCE_DEGREES or abs(there[1] - here[1]) > TOLERANCE_DEGREES:
        raise EngineError("file_not_at_site", "path", f"{path} is for {there}, but the active site {tables.active_site()!r} is at {here}",
                          file_point=there, site_point=here, site=tables.active_site())
