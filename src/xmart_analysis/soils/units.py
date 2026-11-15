"""Ask a soil system about the fields of the panel and keep the answers in a table (`data/learning/soil_units.csv`).

The table is the contract between a soil system and the rest of the project: one row per field with the system's name, the unit's code, its
productivity index and its dominant soil orders. Any adapter that follows `SoilMap` can produce it, so a field in another country is
described the same way. The table is read like any other, and the map itself (CONEAT's is 120 MB) is needed only to refresh it.
"""

from ..engine import tables
from .coneat import write_units
from .ports import SoilUnit

SOURCE_REF = {"coneat": "mgap_coneat"}


def lookup_fields(soil_map, fields):
    """The rows of the table for `fields` ([{field_id, latitude, longitude}]) from a soil map; a field outside the map has no row."""
    points = [(float(f["latitude"]), float(f["longitude"])) for f in fields]
    units = soil_map.lookup_many(points) if hasattr(soil_map, "lookup_many") else [soil_map.lookup(*p) for p in points]
    return [{"field_id": f["field_id"], "system": u.system, "code": u.code, "productivity_index": "" if u.productivity_index is None else u.productivity_index,
             "dominant_orders": ";".join(u.dominant_orders), "source_ref": SOURCE_REF.get(u.system, u.system)}
            for f, u in zip(fields, units) if u is not None]


def load():
    """{field_id: SoilUnit} from the table."""
    return {r["field_id"]: SoilUnit(r["system"], r["code"], float(r["productivity_index"]) if r["productivity_index"] else None,
                                    tuple(o for o in r["dominant_orders"].split(";") if o)) for r in tables.read("learning/soil_units")}


def refresh(soil_map, path):
    """Look up every field of the panel and write the table; returns the rows."""
    rows = lookup_fields(soil_map, tables.read("learning/fields"))
    write_units(rows, path)
    tables.read.cache_clear()
    return rows
