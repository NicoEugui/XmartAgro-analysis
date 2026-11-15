"""What the published models change in the analysis of a field: model B sets the water the scenarios start from, model A sets the risk of each option.

This is the step of the nightly pipeline that uses what was learned from every field of the panel (the registry) on one field:
  B  the satellite's root-zone moisture of the field, corrected (what the other fields taught about satellites on soils like this one, shifted by the
     field's own mean error), takes the place of the sensor series. It enters the engine the way a sensor's readings do (`sensor_sources.apply_history`),
     and the state is then carried to the last day of the climate record.
  A  turns the stress of each crop-season an option counts into the chance the producer calls it bad, normal or good, instead of the fixed cuts; the
     option's drops and risk are those counts. The fixed cuts stay in the result, to compare.
Nothing here is needed to run the engine: without a registry the analysis is the one the fixed rules give.
"""

from datetime import date, datetime, time, timezone
from pathlib import Path

from ..engine import deficit, tables
from ..engine import sensor_input as si
from ..engine import sensor_sources as ss
from ..engine import water_model as wm
from . import examples
from .models import CLASSES
from .registry import Registry
from .stores import SeriesStore

SOURCE = si.CORRECTED_SOURCE  # `water.source` of a start state set by model B
OF_10 = {"bad": "high_deficit", "normal": "moderate_deficit", "good": "low_deficit"}  # model A's classes in the deficit vocabulary


def field_id():
    """The panel field the analysis is about: the active site's own (a real field of the panel has its site's id)."""
    return tables.active_site()


def units(card):
    """The (crop, stress) of every crop-season an option's drops count: a crop's seasons, or every modelled crop-season of a rotation."""
    if card.get("crop_seasons"):
        return [(u["crop"], u["stress"]) for u in card["crop_seasons"]]
    crop = card["id"].split("@")[0]
    return [(crop, s["stress"]) for s in card.get("season_classes") or []]


class Adjustments:
    """The published A and B of a registry folder, applied to one field."""

    def __init__(self, folder, entry_a, model_a, entry_b, model_b):
        self.folder, self.entry_a, self.model_a, self.entry_b, self.model_b = Path(folder), entry_a, model_a, entry_b, model_b

    @classmethod
    def load(cls, folder):
        """The adjustments of a registry folder, or None when there is none or A and B are not both published."""
        if folder is None:
            return None
        registry = Registry(folder)
        a, b = registry.published("A"), registry.published("B")
        return cls(folder, *a, *b) if a and b else None

    # model B -------------------------------------------------------------------------------------------------------------------------

    def corrected_series(self, field=None):
        """{date: moisture} of the field's satellite, corrected by B: the field's first days of satellite-and-sensor overlap give its own shift."""
        field = field or field_id()
        store = SeriesStore(self.folder / "series")
        daily, nodes = store.rows("daily", field), store.rows("nodes", field)
        rows = examples.satellite_rows(daily)
        own = examples.sensor_examples(daily, nodes)[:tables.constant("learn_min_days_b")]
        values = self.model_b.predict(rows, own) if rows else []
        return {date.fromisoformat(r["date"]): round(min(si.MAX_THETA, max(0.0, float(v))), 4) for r, v in zip(rows, values)}

    def start_state(self, info, context, field=None):
        """The sensor description the engine starts from when B's series stands in for the sensor, or `info` itself when the store has no satellite for the field.

        The engine corrects its own water toward each corrected day (the gain of a sensor); from the last satellite day it runs on to the last day
        of the climate record, so the water is today's and not the satellite's last pass."""
        series = self.corrected_series(field)
        if len(series) < 2:
            return info
        history = [{"date": d.isoformat(), "moisture": v} for d, v in sorted(series.items())]
        last = max(series)
        base = {**info, "source": SOURCE, "is_simulated": True, "history": history, "volumetric_moisture": series[last], "timestamp": None,
                "sensor_id": None, "depth_cm": None, "warnings": []}
        corrected = ss.apply_history(base, context)
        end = max(context["weather"])
        if last < end:
            theta = wm.simulate_moisture(context["params"], context["weather"], context["et0"], last, end, corrected["volumetric_moisture"])[end]
            corrected = {**corrected, "volumetric_moisture": theta, "carried_days": (end - last).days,
                         "series": {**corrected["series"], "carried_days": (end - last).days}}
        stamp = datetime.combine(end, time(12), tzinfo=timezone.utc)
        corrected.pop("history", None)  # the series is done: the session must not assimilate it a second time
        return {**corrected, "timestamp": stamp.isoformat(), "model_b": {"version": self.entry_b["version"], "last_satellite_day": last.isoformat()}}

    # model A -------------------------------------------------------------------------------------------------------------------------

    def risk(self, card):
        """The option's drops and water risk by model A and by the fixed cuts, on the crop-seasons the option's drops count; None when it has none."""
        seasons = units(card)
        if not seasons:
            return None
        probabilities = [self.model_a.predict_proba(crop, stress) for crop, stress in seasons]
        counts = {OF_10[name]: float(sum(p[i] for p in probabilities)) for i, name in enumerate(CLASSES)}
        by_cuts = {c: sum(deficit.classify(stress) == c for _, stress in seasons) for c in deficit.CLASSES}
        names = deficit.DROP_NAMES
        drops = {names[k]: v for k, v in deficit.split_in_10(counts, len(seasons)).items()}
        cuts = {names[k]: v for k, v in deficit.split_in_10(by_cuts, len(seasons)).items()}
        return {"model_version": self.entry_a["version"], "seasons": len(seasons), "drops": drops, "water_risk": deficit.water_risk(drops),
                "fixed_cuts_drops": cuts, "fixed_cuts_water_risk": deficit.water_risk(cuts)}
