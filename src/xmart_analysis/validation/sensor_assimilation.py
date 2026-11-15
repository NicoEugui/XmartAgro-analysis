"""Would a soil-moisture sensor improve the water balance? Three simulated experiments, each with a known truth.

The field is simulated (a soil the model does not know, see `engine.sensor_series`), so the error of every run can be measured. The model
receives only the readings. Exploratory and simulated: it measures what a sensor could add, it does not measure a real field.

- `run`: the model blind and corrected by readings every 1, 7 and 30 days, over the last year of the climate.
- `windows`: the same, over every one-year window that fits in the climate record (one start per month), to see how much the gain depends on when the series starts.
- `recalibrate`: fit the soil (wilting point and capacity) to the first part of the series and test it on the rest, with and without correcting the state.
"""

import math
from datetime import date, timedelta
from statistics import median

from ..engine import context as engine_context
from ..engine import sensor_series, soil_fit, tables
from ..engine import water_model as wm


def _errors(model, truth, days=None):
    """RMSE, bias and spread (standard deviation of the error, what is left when a constant offset is removed) against the truth."""
    keys = sorted(truth)[:days]
    gaps = [model[d] - truth[d] for d in keys]
    bias = sum(gaps) / len(gaps)
    return {"rmse": round(math.sqrt(sum(g * g for g in gaps) / len(gaps)), 4), "bias": round(bias, 4),
            "spread": round(math.sqrt(sum((g - bias) ** 2 for g in gaps) / len(gaps)), 4)}


def _model(context, window, observations=None, params=None, start_theta=None):
    start, end = window
    return wm.simulate_moisture(params or context["params"], context["weather"], context["et0"], start, end,
                                tables.constant("simulated_theta") if start_theta is None else start_theta,
                                observations=observations, gain=tables.constant("sensor_gain"))


def run(context=None, path=None):
    context = context or engine_context.build_context()
    readings, truth = sensor_series.load(path), sensor_series.truth(context)
    window = (min(readings), max(readings))
    first_days = tables.constant("sensor_start_window_days")
    open_loop = _model(context, window)
    by_cadence = {days: _model(context, window, sensor_series.every(readings, days)) for days in tables.constant("sensor_cadences")}
    daily = by_cadence[1]
    return {"source": "simulated_sensor", "period": [window[0].isoformat(), window[1].isoformat()], "readings": len(readings),
            "gain": tables.constant("sensor_gain"), "start_window_days": first_days,
            "sensor": {"noise_sd": tables.constant("sensor_noise_sd"), "bias": tables.constant("sensor_bias"), "errors": _errors(readings, truth)},
            "open_loop": {**_errors(open_loop, truth), "first_days_rmse": _errors(open_loop, truth, first_days)["rmse"]},
            "with_sensor": [{"every_days": days, "readings_used": len(sensor_series.every(readings, days)), **_errors(m, truth),
                             "first_days_rmse": _errors(m, truth, first_days)["rmse"]} for days, m in by_cadence.items()],
            "series": [{"date": d.isoformat(), "truth": round(truth[d], 4), "sensor": readings[d], "open_loop": round(open_loop[d], 4),
                        "with_sensor": round(daily[d], 4)} for d in sorted(truth)],
            "note": "simulated field and simulated sensor: shows what a sensor could add, not what it does in a real field"}


def window_starts(weather):
    """The first day of every month from which a full sensor series fits inside the climate record."""
    first, last = min(weather), max(weather)
    length = timedelta(days=tables.constant("sensor_days") - 1)
    day = date(first.year, first.month, 1)
    day = day if day >= first else date(day.year + day.month // 12, day.month % 12 + 1, 1)
    while day + length <= last:
        yield day
        day = date(day.year + day.month // 12, day.month % 12 + 1, 1)


def windows(context=None):
    """The sensor experiment over every one-year window of the climate record, summarised by the month the series starts in."""
    context = context or engine_context.build_context()
    first_days, length = tables.constant("sensor_start_window_days"), timedelta(days=tables.constant("sensor_days") - 1)
    rows = []
    for start in window_starts(context["weather"]):
        window = (start, start + length)
        truth = sensor_series.truth(context, window)
        readings = sensor_series.observe(truth, start)
        blind, corrected = _model(context, window), _model(context, window, readings)
        rows.append({"start": start, "month": start.month, "open_loop": _errors(blind, truth)["rmse"],
                     "with_sensor": _errors(corrected, truth)["rmse"], "open_loop_first": _errors(blind, truth, first_days)["rmse"],
                     "with_sensor_first": _errors(corrected, truth, first_days)["rmse"],
                     "open_loop_bias": _errors(blind, truth)["bias"], "with_sensor_bias": _errors(corrected, truth)["bias"]})
    reduction = [1 - r["with_sensor"] / r["open_loop"] for r in rows]
    by_month = [{"month": m, "windows": len(group), **{k: round(median(r[k] for r in group), 4) for k in
                ("open_loop", "with_sensor", "open_loop_first", "with_sensor_first")}}
                for m in range(1, 13) for group in [[r for r in rows if r["month"] == m]] if group]
    return {"windows": len(rows), "start_window_days": first_days, "first_start": rows[0]["start"].isoformat(), "last_start": rows[-1]["start"].isoformat(),
            "by_start_month": by_month,
            "share_helped": {"whole_year": round(sum(r["with_sensor"] < r["open_loop"] for r in rows) / len(rows), 3),
                             "first_days": round(sum(r["with_sensor_first"] < r["open_loop_first"] for r in rows) / len(rows), 3)},
            "whole_year_reduction": {"median": round(median(reduction), 3), "min": round(min(reduction), 3), "max": round(max(reduction), 3)},
            "bias": {"open_loop": round(median(r["open_loop_bias"] for r in rows), 4), "with_sensor": round(median(r["with_sensor_bias"] for r in rows), 4)},
            "note": "simulated field and sensor over every window of the climate record, one start per month; medians over the windows of each start month"}


def recalibrate(context=None, path=None):
    """Fit the soil to the first part of the series and test it on the rest, against the simulated truth.

    Three soils: the one the model was calibrated with, the one fitted to the readings as they are, and the one fitted to the readings after
    removing the sensor's offset (what one reference measurement, e.g. a soil sample dried and weighed, would make possible; assumed perfect)."""
    context = context or engine_context.build_context()
    readings, truth = sensor_series.load(path), sensor_series.truth(context)
    first, last = min(readings), max(readings)
    split = soil_fit.split_day(first, last)
    offset = tables.constant("sensor_bias")
    referenced = {d: v - offset for d, v in readings.items()}
    soils = {"original": (context["params"], readings), "fitted": (soil_fit.fit(context, readings, first, split)[0], readings),
             "fitted_with_reference": (soil_fit.fit(context, referenced, first, split)[0], referenced)}
    test, window = {d: v for d, v in truth.items() if d > split}, (first, last)
    runs = {}
    for name, (params, series) in soils.items():
        runs[f"{name}_open_loop"] = _model(context, window, params=params, start_theta=series[first])
        runs[f"{name}_corrected"] = _model(context, window, series, params=params, start_theta=series[first])
    names = ("theta_min", "capacity_mm")
    soil = {"simulated_field": sensor_series.truth_params(context["params"]), **{k: v[0] for k, v in soils.items()}}
    return {"period": [first.isoformat(), last.isoformat()], "fit_until": split.isoformat(), "fit_days": (split - first).days + 1,
            "test_days": len(test),
            "soil": {k: {n: round(v, 4) for n, v in zip(names, params[:2])} for k, params in soil.items()},
            "test": {name: _errors(model, test) for name, model in runs.items()}, "sensor_bias": offset,
            "note": "the wilting point absorbs the sensor's offset: a series alone cannot tell the soil from the sensor, that needs a reference measurement"}
