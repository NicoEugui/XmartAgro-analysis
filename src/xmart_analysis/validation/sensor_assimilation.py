"""Would a soil-moisture sensor improve the water balance? Run the model blind and with simulated readings, and compare both with the field.

The field is simulated (a soil the model does not know, see `engine.sensor_series`), so the truth is known and the error of each run can be
measured. The model receives only the readings, every day or every few days, and corrects its water toward them. Exploratory and
simulated: it measures what a sensor could add, it does not measure a real field.
"""

import math

from ..engine import context as engine_context
from ..engine import sensor_series, tables
from ..engine import water_model as wm


def _errors(model, truth, first_days=None):
    days = sorted(truth)[:first_days]
    gaps = [model[d] - truth[d] for d in days]
    return {"rmse": round(math.sqrt(sum(g * g for g in gaps) / len(gaps)), 4), "bias": round(sum(gaps) / len(gaps), 4)}


def run(context=None, path=None):
    context = context or engine_context.build_context()
    readings, truth = sensor_series.load(path), sensor_series.truth(context)
    start, end = min(readings), max(readings)
    gain, start_theta = tables.constant("sensor_gain"), tables.constant("simulated_theta")

    def model(observations=None):
        return wm.simulate_moisture(context["params"], context["weather"], context["et0"], start, end, start_theta,
                                    observations=observations, gain=gain)

    open_loop = model()
    by_cadence = {days: model(sensor_series.every(readings, days)) for days in tables.constant("sensor_cadences")}
    daily = by_cadence[1]
    window = tables.constant("sensor_start_window_days")
    return {"source": "simulated_sensor", "period": [start.isoformat(), end.isoformat()], "readings": len(readings), "gain": gain,
            "sensor": {"noise_sd": tables.constant("sensor_noise_sd"), "bias": tables.constant("sensor_bias"),
                       "errors": _errors(readings, truth)},
            "start_window_days": window,
            "open_loop": {**_errors(open_loop, truth), "first_days_rmse": _errors(open_loop, truth, window)["rmse"]},
            "with_sensor": [{"every_days": days, "readings_used": len(sensor_series.every(readings, days)), **_errors(m, truth),
                             "first_days_rmse": _errors(m, truth, window)["rmse"]} for days, m in by_cadence.items()],
            "series": [{"date": d.isoformat(), "truth": round(truth[d], 4), "sensor": readings[d], "open_loop": round(open_loop[d], 4),
                        "with_sensor": round(daily[d], 4)} for d in sorted(truth)],
            "note": "simulated field and simulated sensor: shows what a sensor could add, not what it does in a real field"}
