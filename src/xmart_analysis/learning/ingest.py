"""The ingest: the only door into the stores. It validates nothing about the model and computes nothing of it; it puts rows in.

`series` fills the series store from the panel's NASA records, satellite and sensor nodes; `examples` builds the examples of A, B and C
and fills the examples store. Both can run any number of times: rows already there are skipped. With real data (a sensor batch, a producer's
form) the same two steps run with those rows instead of the panel's.
"""

from . import examples


def series(panel, store):
    """Load the panel's daily and node rows into the series store; returns {table: (added, skipped)}."""
    daily, nodes = panel.series_rows()
    return {"daily": store.append("daily", daily), "nodes": store.append("nodes", nodes)}


def build_examples(panel, series_store, store):
    """Build the examples of every model from the series store (B) and the panel's seasons (A, C) and load them; returns {model: (added, skipped)}."""
    records = panel.season_records()
    sensor = examples.sensor_examples(series_store.rows("daily"), series_store.rows("nodes"))
    return {"B": store.append("B", sensor), "A": store.append("A", examples.rated(records)), "C": store.append("C", examples.curves(records))}
