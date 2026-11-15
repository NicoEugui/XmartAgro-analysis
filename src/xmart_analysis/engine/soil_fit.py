"""Fit the two soil parameters the sensor can speak about (wilting point and capacity) to a series of readings.

The water balance has more parameters, but a moisture series mainly tells how low the soil dries and how much water it holds, so only
`theta_min` and `capacity_mm` are searched; the rest stay as calibrated. A grid search over the plausible ranges that narrows around the best
point each round: no dependency, deterministic. Whatever offset the sensor has is absorbed by the wilting point, because a series alone cannot
tell soil from sensor: that needs a reference measurement.
"""

import math
from datetime import timedelta

from . import tables
from . import water_model as wm


def bounds():
    """Search ranges: the physically plausible ones the scenarios enforce."""
    return {"theta_min": (tables.constant("wilting_min"), tables.constant("wilting_max")),
            "capacity_mm": (tables.constant("available_water_min"), tables.constant("available_water_max"))}


def _with(params, theta_min, capacity):
    return [theta_min, capacity, *params[2:]]


def _error(context, params, readings, first, last):
    """RMSE between the open-loop model started from the first reading and the readings, from `first` to `last`."""
    model = wm.simulate_moisture(params, context["weather"], context["et0"], first, last, readings[first])
    days = [d for d in model if d in readings]
    return math.sqrt(sum((model[d] - readings[d]) ** 2 for d in days) / len(days))


def fit(context, readings, first, last):
    """(params, rmse): the model's parameters with the wilting point and capacity that best follow the readings from `first` to `last`."""
    ranges = {name: list(r) for name, r in bounds().items()}
    points, best = tables.constant("fit_grid_points"), None
    for _ in range(tables.constant("fit_rounds")):
        grid = {name: [lo + (hi - lo) * i / (points - 1) for i in range(points)] for name, (lo, hi) in ranges.items()}
        best = min(((_error(context, _with(context["params"], t, c), readings, first, last), t, c)
                    for t in grid["theta_min"] for c in grid["capacity_mm"]), key=lambda r: r[0])
        for name, value, values in (("theta_min", best[1], grid["theta_min"]), ("capacity_mm", best[2], grid["capacity_mm"])):
            step = values[1] - values[0]
            ranges[name] = [max(bounds()[name][0], value - step), min(bounds()[name][1], value + step)]
    error, theta_min, capacity = best
    return _with(context["params"], theta_min, capacity), error


def split_day(first, last):
    """The last day used to fit; the days after it test the fit."""
    return first + timedelta(days=int((last - first).days * tables.constant("sensor_train_share")))
