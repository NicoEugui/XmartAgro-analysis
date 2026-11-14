"""Guard for NASA exports: a file downloaded for one point must not be validated against another site."""

import csv

from ..engine import tables
from ..engine.errors import EngineError

TOLERANCE_DEGREES = 0.05


def check_coordinates(path, latitude, longitude, tolerance=TOLERANCE_DEGREES):
    """Raise if (latitude, longitude) is not the active site's point."""
    here = (tables.constant("latitude"), tables.constant("longitude"))
    if abs(latitude - here[0]) > tolerance or abs(longitude - here[1]) > tolerance:
        raise EngineError("file_not_at_site", "path", f"{path} is for {(latitude, longitude)}, but the active site "
                          f"{tables.active_site()!r} is at {here}", file_point=(latitude, longitude), site_point=here,
                          site=tables.active_site())


def check_point(path):
    """Raise if the file states a Latitude/Longitude that is not the active site's point (files without them pass)."""
    with open(path, newline="") as stream:
        row = next(csv.DictReader(stream), None)
    if not row or "Latitude" not in row or "Longitude" not in row:
        return
    check_coordinates(path, float(row["Latitude"]), float(row["Longitude"]))
