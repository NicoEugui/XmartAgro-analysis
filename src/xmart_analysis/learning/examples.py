"""The stores of examples the models learn from (a row is a plain dict; every row of the panel says it is simulated).

B: a field on a day (satellite value, field traits, time of year) with the calibrated node moisture as the answer.
A: a field in a season (the stress the model computed, the crop) with the producer's rating as the answer.
C: a field in a season (the five numbers of its NDVI curve) with the crop, or fallow, as the answer.
"""

import math
from datetime import date
from functools import cached_property

from ..engine import context as engine_context
from ..engine import crops_uy as cu  # noqa: F401  (the crops the panel covers are in crop_ranges.csv)
from ..engine import sensor_series, tables
from . import fields, nodes, outcomes, producers


class Panel:
    """The fields of the panel with their contexts, built once. `sites` is {site id: context} of the real NASA sites."""

    def __init__(self, sites=None):
        self.fields = fields.all_fields()
        self.sites = sites or {site: engine_context.build_context(site) for site in fields.real_sites()}

    @cached_property
    def contexts(self):
        return {f.field_id: fields.build_context(f, self.sites) for f in self.fields}

    def series_rows(self):
        """The rows of the series store: ({field, day} climate and satellite, {node, day} readings), for every field."""
        daily, readings = [], []
        for field in self.fields:
            context = self.contexts[field.field_id]
            window = sensor_series.span(context["weather"])
            satellite = fields.smap(field, context, window)
            for day, w in sorted(context["weather"].items()):
                daily.append({"field_id": field.field_id, "date": str(day), "rain_mm": round(w["PRECTOTCORR"], 3), "t2m": round(w["T2M"], 2),
                              "t2m_min": round(w["T2M_MIN"], 2), "t2m_max": round(w["T2M_MAX"], 2), "smap_rootzone": satellite.get(day),
                              "climate_source": "nasa_power", "satellite_simulated": not field.real})
            for node in nodes.of_field(field.field_id):
                raw = nodes.readings(node, field, context, window)
                fixed = nodes.calibrated(node, raw)
                readings += [{"node_id": node.node_id, "field_id": field.field_id, "date": str(day), "depth_cm": node.depth_cm,
                              "raw_moisture": raw[day], "calibrated_moisture": fixed[day], "source": outcomes.SOURCE, "simulated": True}
                             for day in sorted(raw)]
        return daily, readings

    def sensor_rows(self):
        """Examples for B built from this panel's series."""
        return sensor_examples(*self.series_rows())

    def season_records(self):
        """The 60 seasons of the twelve producers, then every crop in every field and historical season (the national panel)."""
        by_id = {f.field_id: f for f in self.fields}
        out = []
        for producer in producers.all_producers():
            field = by_id[producer.field_id]
            out += [r for year, crop in producers.seasons(producer)
                    if (r := outcomes.record(field, self.contexts[field.field_id], crop, year, producer))]
        for field in self.fields:
            for crop in producers.crop_ranges():
                out += [r for year in tables.season_years() if (r := outcomes.record(field, self.contexts[field.field_id], crop, year))]
            out += [outcomes.record(field, self.contexts[field.field_id], producers.FALLOW, year) for year in tables.season_years()]
        return out


def satellite_rows(daily):
    """What model B needs about each field-day with a satellite value: the value and the field's traits, ordered by date (no sensor needed)."""
    by_field = {f.field_id: f for f in fields.all_fields()}
    rows = []
    for r in sorted(daily, key=lambda r: r["date"]):
        if r["smap_rootzone"] is None:
            continue
        field, angle = by_field[r["field_id"]], 2 * math.pi * date.fromisoformat(r["date"]).timetuple().tm_yday / 365
        rows.append({"source": outcomes.SOURCE, "simulated": True, "satellite_simulated": r["satellite_simulated"], "field_id": r["field_id"],
                     "date": r["date"], "smap": r["smap_rootzone"], "clay": field.clay, "slope_pct": field.slope_pct,
                     "season_sin": math.sin(angle), "season_cos": math.cos(angle)})
    return rows


def sensor_examples(daily, node_rows):
    """Examples for B from the series store's rows: a field's day with a satellite value and calibrated nodes, as the field's mean."""
    calibrated = {}
    for r in node_rows:
        calibrated.setdefault((r["field_id"], r["date"]), []).append(r["calibrated_moisture"])
    return [{**row, "sensor": round(sum(calibrated[key]) / len(calibrated[key]), 4)}
            for row in satellite_rows(daily) if (key := (row["field_id"], row["date"])) in calibrated]


def rated(records):
    """Examples for A: the seasons that have a producer's rating, with the three classes."""
    return [{**r, "class": outcomes.CLASS_OF_RATING[r["rating"] - 1]} for r in records if r["rating"] is not None]


def curves(records):
    """Examples for C: the five numbers of each season's curve and what grew."""
    return [{**r["ndvi"], "source": r["source"], "simulated": True, "field_id": r["field_id"], "producer_id": r["producer_id"],
             "season": r["season"], "crop": r["crop"]} for r in records]
