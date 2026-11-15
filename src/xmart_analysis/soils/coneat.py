"""Uruguay's CONEAT soil groups (MGAP): the adapter that answers "which group is this point in?" from the official shapefile.

The map is a layer of polygons in UTM zone 21S whose attribute `SC` is the group code. The shapefile is large (about 120 MB) and is not
kept in the repository: the adapter reads the copy the user has, once for any number of points, and the groups' own data (productivity index,
dominant soil orders) comes from the small table `data/soils/coneat_groups.csv`. Needs `pyshp` and `pyproj` (extra `coneat`).
"""

import csv
from pathlib import Path

from ..engine import tables
from . import groups
from .ports import SoilUnit

SYSTEM = "coneat"
UTM_21S = 32721  # WGS 84 / UTM zone 21S, the map's projection (its .prj says so)
CODE_FIELD = "SC"


def load_groups():
    """{group code: SoilUnit} from the committed table."""
    out = {}
    for row in tables.read("soils/coneat_groups"):
        index = float(row["productivity_index"]) if row["productivity_index"] else None
        out[row["code"]] = SoilUnit(SYSTEM, row["code"], index, tuple(o for o in row["dominant_orders"].split(";") if o))
    return out


def _inside(x, y, points, parts):
    """Even-odd test of a point against a polygon with several rings (holes count)."""
    inside = False
    for start, end in zip(parts, [*parts[1:], len(points)]):
        ring = points[start:end]
        j = len(ring) - 1
        for i, (xi, yi) in enumerate(ring):
            xj, yj = ring[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
    return inside


class ConeatMap:
    system = SYSTEM

    def __init__(self, shapefile, epsg=UTM_21S):
        try:
            import shapefile as pyshp
            from pyproj import Transformer
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(f"CONEAT needs pyshp and pyproj: pip install 'xmartagro-analysis[coneat]' ({exc.name})") from exc
        self._pyshp, self.path = pyshp, Path(shapefile)
        self._transform = Transformer.from_crs(4326, epsg, always_xy=True).transform
        self.groups = load_groups()

    def lookup_many(self, points):
        """The unit of each (latitude, longitude), in order, from one pass over the map (None where no polygon holds the point)."""
        xy = [self._transform(lon, lat) for lat, lon in points]
        found = {}
        reader = self._pyshp.Reader(str(self.path), encoding="utf-8")
        for record in reader.iterShapeRecords(fields=[CODE_FIELD]):
            shape = record.shape
            for i, (x, y) in enumerate(xy):
                if i not in found and shape.bbox[0] <= x <= shape.bbox[2] and shape.bbox[1] <= y <= shape.bbox[3] \
                        and _inside(x, y, shape.points, shape.parts):
                    found[i] = groups.normalize(str(record.record[CODE_FIELD]).strip())
            if len(found) == len(xy):
                break
        return [self.groups.get(found[i]) if i in found else None for i in range(len(xy))]

    def lookup(self, latitude, longitude):
        return self.lookup_many([(latitude, longitude)])[0]


def write_units(rows, path):
    """Write the units found for the fields: {field_id, system, code, productivity_index, dominant_orders, source_ref}."""
    columns = ("field_id", "system", "code", "productivity_index", "dominant_orders", "source_ref")
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
