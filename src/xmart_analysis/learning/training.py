"""Training cycle: build the examples, validate every model on fields kept apart, fit on all, register and report.

The report says what the numbers mean: with a simulated panel they show the models recover a structure planted on purpose
(and that the cycle, the validation and the registry work), not accuracy on real fields."""

from pathlib import Path

from ..engine import tables
from . import examples, ingest, models, soil_health, validation
from .registry import Registry
from .stores import ExamplesStore, SeriesStore


def datasets(panel):
    """{model name: rows} for every model."""
    records = panel.season_records()
    return {"B": panel.sensor_rows(), "A": examples.rated(records), "C": examples.curves(records)}


def load_stores(folder, panel):
    """Fill the series and examples stores under `folder` (rows already there are skipped); returns the stores and what each load added."""
    series, store = SeriesStore(Path(folder) / "series"), ExamplesStore(Path(folder) / "examples")
    loaded = {"series": ingest.series(panel, series), "examples": ingest.build_examples(panel, series, store)}
    return series, store, loaded


def train(folder, trained_on, panel=None, only=None):
    """Train the models (all, or those named in `only`) on the examples store, register them in `folder` and return the report."""
    panel = panel or examples.Panel()
    _, store, loaded = load_stores(folder, panel)
    data = {name: store.rows(name) for name in models.MODELS}
    registry, report = Registry(folder), {}
    for name, make in models.MODELS.items():
        if only and name not in only:
            continue
        rows = data[name]
        check = validation.holdout(make, rows)
        entry = registry.register(make().fit(rows), check, len(rows), len({r["field_id"] for r in rows}), trained_on,
                                  make().ready(rows), all(r["simulated"] for r in rows))
        report[name] = {k: entry[k] for k in ("version", "state", "reason", "n_examples", "n_fields", "simulated_data", "validation")}
    return {"trained_on": trained_on, "folder": str(folder), "data": {k: len(v) for k, v in data.items()}, "loaded": loaded,
            "fields": [{"field_id": f.field_id, "real": f.real} for f in panel.fields],
            "constants": {k: tables.constant(k) for k in ("learn_holdout_share", "learn_holdout_rounds", "learn_pool_k_a", "learn_pool_k_b")},
            "models": report, "soil_health": soil_health.producer_table(),
            "reading": "simulated panel: the metrics say the models recover the structure planted in the simulation, not how accurate they are on real fields"}
