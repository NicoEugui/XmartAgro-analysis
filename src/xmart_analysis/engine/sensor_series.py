"""A series of soil-moisture readings: how the engine reads one, and how a simulated year is made until real sensors exist.

The simulated field ("truth") is the same bucket with a soil the model does not know (another capacity and wilting point). The sensor
measures that field with noise and a constant offset. The model only ever receives the readings, never the truth, so comparing it with
the truth says whether a sensor would help. A real ESP32 export with the columns `date` and `volumetric_moisture` is read by the same
`load`, so the data can be swapped without touching the model.
"""

import csv
import random
from datetime import date, timedelta

from . import tables
from . import water_model as wm
from .sensor_input import MAX_THETA, validate_theta

SOURCE_FILE = "sensor_simulated.csv"
SENSOR_ID = "simulated-01"
COLUMNS = ("date", "volumetric_moisture", "sensor_id")


def default_path():
    return tables.site_file(SOURCE_FILE)


def span(weather):
    """First and last day of the series: the last `sensor_days` days of the climate record, so it runs up to the newest day there is."""
    end = max(weather)
    return end - timedelta(days=tables.constant("sensor_days") - 1), end


def truth_params(params):
    """The simulated field's soil: the model's parameters with another wilting point and capacity."""
    theta_min, capacity, *rest = params
    return [theta_min + tables.constant("sensor_truth_theta_min_shift"),
            capacity * tables.constant("sensor_truth_capacity_factor"), *rest]


def truth(context, window=None):
    """{date: moisture} of the simulated field over `window` ((first, last) days; the last year of the climate by default)."""
    start, end = window or span(context["weather"])
    return wm.simulate_moisture(truth_params(context["params"]), context["weather"], context["et0"], start, end,
                                tables.constant("sensor_truth_start_theta"))


def observe(field, first_day):
    """{date: moisture} the simulated sensor reports for a field ({date: moisture}): the truth plus a constant offset and Gaussian
    noise, within the possible range.

    The noise is seeded by the seed and the first day, so every window has its own noise and the same window always gets the same."""
    noise = random.Random(f"{tables.constant('sensor_seed')}:{first_day}")
    bias, sd = tables.constant("sensor_bias"), tables.constant("sensor_noise_sd")
    return {day: round(min(MAX_THETA, max(0.0, theta + bias + noise.gauss(0, sd))), 4) for day, theta in sorted(field.items())}


def readings(context, window=None):
    """{date: moisture} the simulated sensor reports over `window` (the last year of the climate by default)."""
    window = window or span(context["weather"])
    return observe(truth(context, window), window[0])


def assimilate(context, readings, gain=None):
    """{date: modeled moisture}: the model run over the days of `readings` ({date: reading}), corrected toward each reading by the gain.

    The first reading is the starting state; every day needs climate (the caller checks). One function for the experiment's
    runs and for the state the demo starts from."""
    first, last = min(readings), max(readings)
    return wm.simulate_moisture(context["params"], context["weather"], context["et0"], first, last, readings[first],
                                observations=readings, gain=tables.constant("sensor_gain") if gain is None else gain)


def write(path, series):
    with open(path, "w", newline="", encoding="utf-8") as stream:
        out = csv.writer(stream, lineterminator="\n")
        out.writerow(COLUMNS)
        out.writerows((day.isoformat(), theta, SENSOR_ID) for day, theta in sorted(series.items()))


def load(path=None):
    """{date: moisture} from a readings file; a reading outside the possible range stops the run."""
    with open(path or default_path(), newline="", encoding="utf-8") as stream:
        return {date.fromisoformat(r["date"]): validate_theta(float(r["volumetric_moisture"])) for r in csv.DictReader(stream)}


def every(series, days):
    """The readings a sensor that reports every `days` days (starting with the first) would give."""
    return {day: theta for i, (day, theta) in enumerate(sorted(series.items())) if i % days == 0}
