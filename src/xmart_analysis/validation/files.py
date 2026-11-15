"""Guard for NASA exports: a file downloaded for one point must not be validated against another site."""

import csv

from ..engine import tables
from ..engine.errors import EngineError

TOLERANCE_DEGREES = 0.05


def check_coordinates(path, latitude, longitude, tolerance=TOLERANCE_DEGREES, site_id=None):
    """Raise if (latitude, longitude) is not the point of the site (the active one by default)."""
    site_id = site_id or tables.active_site()
    here = (tables.constants_of(site_id)["latitude"], tables.constants_of(site_id)["longitude"])
    if abs(latitude - here[0]) > tolerance or abs(longitude - here[1]) > tolerance:
        raise EngineError("file_not_at_site", "path", f"{path} is for {(latitude, longitude)}, but the active site "
                          f"{site_id!r} is at {here}", file_point=(latitude, longitude), site_point=here,
                          site=site_id)


def check_point(path, site_id=None):
    """Raise if the file states a Latitude/Longitude that is not the site's point (files without them pass)."""
    with open(path, newline="") as stream:
        row = next(csv.DictReader(stream), None)
    if not row or "Latitude" not in row or "Longitude" not in row:
        return
    check_coordinates(path, float(row["Latitude"]), float(row["Longitude"]), site_id=site_id)
