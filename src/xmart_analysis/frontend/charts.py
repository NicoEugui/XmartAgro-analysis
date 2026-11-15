"""The data behind the figures of the experiment log, in one language-neutral format the frontend can draw (`charts` in frontend.json).

A chart is columnar: one shared list of `x.values` and, for each series, a `values` list of the same length (null where a value is missing).
Every figure of `reports/experiments.md` becomes one or more charts built from the very same documents (`from_documents`), so the numbers the
frontend draws are the numbers the figures plot; a test checks that every value in a figure's table is in the charts. Sensor charts are flagged
`simulated`. A text is `{key, en, es}` like everywhere else in the payload.
"""

import copy
from functools import cache

from ..engine import context as engine_context
from ..engine import crops_uy, tables
from ..engine.i18n import label
from ..report import scenario_runs
from ..validation import documents

UNIT_MOISTURE = "m3/m3"


def _chart(chart_id, figure, group, title, x, y, series, source, stacked=False, simulated=False, note=None):
    return {"id": chart_id, "figure": figure, "group": group, "title": title, "note": note, "x": x, "y": y, "stacked": stacked,
            "simulated": simulated, "source": source, "series": series}


def _x(kind, values, name=None, names=None, tags=None):
    return {"type": kind, "label": name, "values": list(values), "names": names, "tags": tags}


def _y(name=None, unit=None):
    return {"label": name, "unit": unit}


def _s(series_id, name, style, values):
    return {"id": series_id, "label": name, "style": style, "values": list(values)}


def _crop(crop):
    return label(crops_uy.name_label_key(crop))


def sensor(doc):
    rows = doc["series"]
    dates = [r["date"] for r in rows]
    runs = [("open_loop", label("sensor.run.open_loop"), doc["open_loop"])] + [
        (f"every_{r['every_days']}", label("sensor.run.every", days=r["every_days"]), r) for r in doc["with_sensor"]]
    common = {"source": "simulated_sensor", "simulated": True, "note": label("sensor.note")}
    return [
        _chart("sensor_series", "sensor", "sensor", label("sensor.title"), _x("date", dates), _y(label("sensor.axis.moisture"), UNIT_MOISTURE),
               [_s("readings", label("sensor.series.readings"), "points", [r["sensor"] for r in rows]),
                _s("truth", label("sensor.series.truth"), "line", [r["truth"] for r in rows]),
                _s("open_loop", label("sensor.series.open_loop"), "line", [r["open_loop"] for r in rows]),
                _s("with_sensor", label("sensor.series.with_sensor"), "line", [r["with_sensor"] for r in rows])], **common),
        _chart("sensor_errors", "sensor", "sensor", label("chart.sensor_errors.title"),
               _x("category", [k for k, _, _ in runs], names=[n for _, n, _ in runs]), _y(label("sensor.axis.rmse"), UNIT_MOISTURE),
               [_s("whole_year", label("sensor.bar.year"), "bar", [e["rmse"] for _, _, e in runs]),
                _s("first_days", label("sensor.bar.start", days=doc["start_window_days"]), "bar", [e["first_days_rmse"] for _, _, e in runs])], **common)]


def sensor_windows(doc):
    months = [r["month"] for r in doc["by_start_month"]]
    common = {"source": "simulated_sensor", "simulated": True, "note": label("sensor_windows.note")}
    return [_chart(chart_id, "sensor_windows", "sensor", title, _x("number", months, label("sensor_windows.start_month")), _y(label("sensor.axis.rmse"), UNIT_MOISTURE),
                   [_s("no_sensor", label("sensor_windows.no_sensor"), "bar", [r[blind] for r in doc["by_start_month"]]),
                    _s("daily_sensor", label("sensor_windows.daily"), "bar", [r[sensor] for r in doc["by_start_month"]])], **common)
            for chart_id, title, blind, sensor in (("sensor_windows_whole", label("sensor_windows.whole"), "open_loop", "with_sensor"),
                                                   ("sensor_windows_first", label("sensor_windows.first", days=doc["start_window_days"]), "open_loop_first", "with_sensor_first"))]


def sensor_recalibration(doc):
    soils = ("original", "fitted", "fitted_with_reference")
    return [_chart(f"sensor_recal_{metric}", "sensor_recalibration", "sensor", label(f"sensor_recal.{metric}"),
                   _x("category", soils, names=[label(f"sensor_recal.{s}") for s in soils]), _y(None, UNIT_MOISTURE),
                   [_s(mode, label(f"sensor_recal.{mode}"), "bar", [doc["test"][f"{s}_{mode}"][metric] for s in soils]) for mode in ("open_loop", "corrected")],
                   source="simulated_sensor", simulated=True, note=label("sensor_recal.note")) for metric in ("rmse", "bias", "spread")]


def rain_decision(doc):
    imerg, sens = doc["imerg"], doc["sensitivity"]
    power, satellite = label("validation.imerg.source_power"), label("validation.imerg.source_imerg")
    cycle, stress = imerg["monthly_mean_mm"], sens["crops"][sens["first_crop"]]["stress"]
    shares = sens["rotations_high_deficit_share"]
    common = {"group": "rain", "source": "gpm_imerg", "note": label("rain_decision.note")}
    charts = [
        _chart("rain_monthly", "rain_decision", title=label("rain_decision.monthly"), x=_x("number", [r["month"] for r in cycle], label("rain_decision.month")),
               y=_y(None, "mm"), series=[_s("power", power, "bar", [r["power"] for r in cycle]), _s("imerg", satellite, "bar", [r["imerg"] for r in cycle])], **common),
        _chart("rain_stress", "rain_decision", title=label("rain_decision.stress"), x=_x("category", [r["season"] for r in stress]),
               y=_y(label("rain_decision.stress_axis")), series=[_s("power", power, "points", [r["power"] for r in stress]),
                                                                  _s("imerg", satellite, "points", [r["imerg"] for r in stress])], **common)]
    for crop, entry in sens["crops"].items():
        counts = entry["class_counts"]
        charts.append(_chart(f"rain_classes_{crop}", "rain_decision", title=label("chart.rain_classes.title", crop=_crop(crop)),
                             x=_x("category", ["power", "imerg"]), y=_y(label("sowing.axis.seasons")), stacked=True,
                             series=[_s(name, label(f"sowing.drop.{name}"), "bar", [counts["power"][name], counts["imerg"][name]]) for name in ("ok", "tight", "out")], **common))
    charts.append(_chart("rain_rotations", "rain_decision", title=label("rain_decision.rotations"), x=_x("category", list(shares)), y=_y(),
                         series=[_s("power", power, "bar", [v["power"] for v in shares.values()]), _s("imerg", satellite, "bar", [v["imerg"] for v in shares.values()])], **common))
    return charts


def imerg(doc):
    seasons = doc["seasons_dec_mar"]
    return [_chart("imerg_seasons", "imerg", "rain", label("chart.imerg_seasons.title"), _x("category", [r["season"] for r in seasons]), _y(None, "mm"),
                   [_s("power", label("validation.imerg.source_power"), "bar", [r["power_mm"] for r in seasons]),
                    _s("imerg", label("validation.imerg.source_imerg"), "bar", [r["imerg_mm"] for r in seasons])], source="gpm_imerg", note=label("validation.note.imerg"))]


def survey(doc):
    seasons = doc["window"]
    common = {"group": "validation", "source": "producer_survey", "note": label("validation.note.survey", answered=doc["answered"], total=doc["respondents"])}
    return [_chart("survey_mentions", "survey", title=label("validation.title.survey"), x=_x("category", seasons), y=_y(label("validation.axis.mentions")),
                   series=[_s("mentions", label("validation.axis.mentions"), "bar", [doc["mentions"][s] for s in seasons])], **common),
            _chart("survey_stress", "survey", title=label("validation.title.survey"), x=_x("category", seasons), y=_y(label("validation.axis.critical_stress")),
                   series=[_s(crop, label(f"validation.crop.{crop}"), "bar", [entry["stress"][s] for s in seasons]) for crop, entry in doc["crops"].items()], **common)]


def smap(doc):
    scores = doc["periods"]["validation"]["scores"]
    return [_chart(f"smap_{metric}", "smap", "validation", label(f"validation.metric.{key}"),
                   _x("category", list(scores), names=[label(f"validation.predictor.{n}") for n in scores]), _y(),
                   [_s(metric, label(f"validation.metric.{key}"), "bar", [s[metric] for s in scores.values()])], source="smap_l3", note=label("validation.note.smap"))
            for metric, key in (("spearman", "spearman"), ("anomaly_r", "anomaly"))]


def ndvi(doc):
    rows = doc["seasons"]
    return [_chart(f"ndvi_{crop}", "ndvi", "validation", label("validation.title.ndvi"), _x("number", [r["ndvi_dec_mar"] for r in rows], label("validation.axis.ndvi"),
                                                                                         tags=[r["season"] for r in rows]),
                   _y(label("validation.axis.critical_stress")), [_s(crop, label(f"validation.crop.{crop}"), "points", [r[f"{crop}_stress"] for r in rows])],
                   source="modis_ndvi", note=label("validation.note.ndvi")) for crop in ("soybean_1st", "maize")]


def sowing(doc):
    note = label("sowing.note")
    charts = [_chart(f"sowing_{crop}", "sowing", "sowing", label("chart.sowing.title", crop=_crop(crop)), _x("month_day", [r["sowing"] for r in entry["dates"]]),
                     _y(label("sowing.axis.seasons")), [_s(name, label(f"sowing.drop.{name}"), "bar", [r["counts"][name] for r in entry["dates"]]) for name in ("ok", "tight", "out")],
                     source="nasa_power", stacked=True, simulated=True, note=note) for crop, entry in doc["crops"].items()]
    detail, reading = doc["detail"], doc["reading_sensitivity"]
    charts.append(_chart("sowing_detail", "sowing", "sowing", label("chart.sowing_detail.title", crop=_crop(detail["crop"])), _x("category", [r["season"] for r in detail["seasons"]]),
                         _y(label("validation.axis.critical_stress")), [_s("stress", label("validation.axis.critical_stress"), "bar", [r["stress"] for r in detail["seasons"]])],
                         source="nasa_power", simulated=True, note=note))
    charts.append(_chart("sowing_reading", "sowing", "sowing", label("chart.sowing_reading.title", crop=_crop(reading["crop"])),
                         _x("number", [r["volumetric_moisture"] for r in reading["readings"]], label("chart.reading.axis")), _y(label("sowing.axis.seasons")),
                         [_s(name, label(f"sowing.drop.{name}"), "bar", [r["counts"][name] for r in reading["readings"]]) for name in ("ok", "tight", "out")],
                         source="nasa_power", stacked=True, simulated=True, note=note))
    return charts


def retrospective(doc):
    feat = doc["featured"]
    rows, crops = feat["rows"], doc["crops"]
    departments = {f["field_id"]: f["department"] for f in tables.read("learning/fields")}
    proper = lambda name: {"key": f"department.{name}", "en": name, "es": name}  # noqa: E731  (a place name reads the same in both languages)
    x = _x("category", [r["field_id"] for r in rows], names=[proper(departments[r["field_id"]]) for r in rows])
    common = {"group": "retrospective", "source": "simulated_panel", "simulated": True, "note": label("retro.note")}
    return [
        _chart("retro_drops", "retrospective", title=label("retro.drops", crop=_crop(feat["crop"]), season=feat["season"]), x=x, y=_y(label("sowing.axis.seasons")), stacked=True,
               series=[_s(name, label(f"sowing.drop.{name}"), "bar", [r["drops"][name] for r in rows]) for name in ("ok", "tight", "out")], **common),
        _chart("retro_actual", "retrospective", title=label("retro.actual"), x=x, y=_y(label("validation.axis.critical_stress")),
               series=[_s("actual_stress", label("retro.actual"), "bar", [r["actual_stress"] for r in rows])], **common),
        _chart("retro_share", "retrospective", title=label("retro.title"), x=_x("category", list(crops), names=[_crop(c) for c in crops]), y=_y(label("retro.share_axis")),
               series=[_s("base_rate", label("retro.base"), "bar", [doc["by_crop"][c]["base_rate_out"] for c in crops]),
                       _s("warned", label("retro.warned"), "bar", [doc["by_crop"][c]["warned_of_out"] for c in crops])], **common)]


BUILDERS = {"retrospective": retrospective, "sowing": sowing, "survey": survey, "smap": smap, "ndvi": ndvi, "imerg": imerg, "rain_decision": rain_decision,
            "sensor": sensor, "sensor_windows": sensor_windows, "sensor_recalibration": sensor_recalibration}


def from_documents(docs):
    """The charts of every document given, in a fixed order (a document that is missing leaves its charts out)."""
    return [chart for name, build in BUILDERS.items() if name in docs for chart in build(docs[name])]


@cache
def _build():
    context = engine_context.build_context()
    return from_documents({**documents.bundled(context), "sowing": scenario_runs.run(context)})


def build():
    """The charts of this checkout with the NASA files bundled for the site (computed once)."""
    return copy.deepcopy(_build())
