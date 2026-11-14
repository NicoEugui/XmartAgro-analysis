"""Is the NASA POWER climate the model runs on consistent with a real weather station?

Station: INIA La Estanzuela daily record (`data/validation/station_la_estanzuela.csv`, rain, air temperature, Penman ET).
It is at the same location as the NASA point, so what limits daily agreement is the 0.5 x 0.625 degree grid cell; what
matters for the water balance is monthly and seasonal rain, and the evaporative demand. Compared over the whole POWER record.
"""

import csv
from collections import defaultdict
from datetime import date, timedelta

from ..engine import context as engine_context
from ..engine import tables
from ..engine import water_model as wm
from ..engine import water_scenarios as ws
from .stats import pearson, spearman

STATION_FILE = lambda: tables.site_file("station_daily.csv")  # noqa: E731 - resolved per active site
SOURCE_COLUMNS = {"rain_mm": "Precip. Acumulada (mm)", "tmax_c": "Temp. Aire Máxima (ºC)", "tmin_c": "Temp. Aire Mìnima (ºC)",
                  "penman_et_mm": "Evapotransp. Penman (mm)", "solar_cal_cm2": "Rad.Solar (xHelio)cal/cm²"}
WET_DAY_MM = 1.0
SEASON_DAYS = 121  # 1 December to 31 March


def import_station(source_csv, target_csv, first_day=date(1986, 7, 1)):
    """Keep the daily columns the model can use from a station export (header on line 2, notes after the data)."""
    lines = open(source_csv, encoding="utf-8").read().splitlines()
    header = lines[1].split(",")
    rows = []
    for line in lines[2:]:
        if len(line) > 9 and line[4] == "-" and line[7] == "-" and date.fromisoformat(line[:10]) >= first_day:
            record = dict(zip(header, next(csv.reader([line]))))
            rows.append([record["Fecha"]] + [record[column] for column in SOURCE_COLUMNS.values()])
    with open(target_csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["date", *SOURCE_COLUMNS])
        writer.writerows(rows)
    return len(rows)


def available():
    """Whether the active site has a weather station dataset."""
    return STATION_FILE().exists()


def load(path=None):
    """{date: {column: value or None}}."""
    path = path or STATION_FILE()
    with open(path, newline="", encoding="utf-8") as stream:
        return {date.fromisoformat(r["date"]): {k: float(v) if v not in ("", "NaN") else None for k, v in r.items() if k != "date"}
                for r in csv.DictReader(stream)}


def paired(station, weather, column, power_value):
    days = [d for d in sorted(weather) if d in station and station[d][column] is not None]
    return days, [station[d][column] for d in days], [power_value(d) for d in days]


def monthly_totals(days, a, b):
    out = defaultdict(lambda: [0.0, 0.0])
    for d, x, y in zip(days, a, b):
        out[(d.year, d.month)][0] += x
        out[(d.year, d.month)][1] += y
    return [v[0] for v in out.values()], [v[1] for v in out.values()]


def season_rain(series, year):
    return sum(series[d] for d in (date(year, 12, 1) + timedelta(days=i) for i in range(SEASON_DAYS)) if d in series)


def fit_et0_scale(weather, station=None):
    """Factor that makes the model's Hargreaves ET0 match the station's Penman ET on average (ratio of totals)."""
    station = station or load()
    raw = wm.precompute_et0(weather, scale=1.0)
    days = [d for d in weather if d in station and station[d]["penman_et_mm"] is not None]
    return sum(station[d]["penman_et_mm"] for d in days) / sum(raw[d] for d in days)


def run(context=None, station=None):
    context = context or engine_context.build_context()
    weather = context["weather"]
    station = station or load()
    et0 = wm.precompute_et0(weather, scale=1.0)  # uncorrected Hargreaves: the correction is fitted to this very comparison
    days, rain_s, rain_p = paired(station, weather, "rain_mm", lambda d: weather[d]["PRECTOTCORR"])
    month_s, month_p = monthly_totals(days, rain_s, rain_p)
    years = ws.SEASON_YEARS
    rain_by_day_s = {d: station[d]["rain_mm"] for d in days}
    rain_by_day_p = {d: weather[d]["PRECTOTCORR"] for d in days}
    season_s = [season_rain(rain_by_day_s, y) for y in years]
    season_p = [season_rain(rain_by_day_p, y) for y in years]
    rain = {"days": len(days), "daily_r": round(pearson(rain_s, rain_p), 3), "monthly_r": round(pearson(month_s, month_p), 3),
            "season_dec_mar_r": round(pearson(season_s, season_p), 3), "season_dec_mar_rho": round(spearman(season_s, season_p), 3),
            "mean_annual_mm": {"station": round(sum(rain_s) / len(days) * 365.25), "power": round(sum(rain_p) / len(days) * 365.25)},
            "wet_day_share": {"station": round(sum(v >= WET_DAY_MM for v in rain_s) / len(rain_s), 3),
                              "power": round(sum(v >= WET_DAY_MM for v in rain_p) / len(rain_p), 3)}}
    temperature = {}
    for name, key in (("tmax_c", "T2M_MAX"), ("tmin_c", "T2M_MIN")):
        d_, s_, p_ = paired(station, weather, name, lambda d, key=key: weather[d][key])
        temperature[name] = {"daily_r": round(pearson(s_, p_), 3), "power_minus_station_c": round(sum(p - s for s, p in zip(s_, p_)) / len(s_), 2)}
    d_, pen, harg = paired(station, weather, "penman_et_mm", lambda d: et0[d])
    et = {"days": len(d_), "daily_r": round(pearson(pen, harg), 3), "mean_mm_day": {"station_penman": round(sum(pen) / len(pen), 2),
          "hargreaves_uncorrected": round(sum(harg) / len(harg), 2)}, "model_over_station": round(sum(harg) / sum(pen), 3),
          "applied_scale": tables.constant("et0_scale"), "scale_fitted_here": round(fit_et0_scale(weather, station), 4)}
    seasons = [{"season": ws.season_name(y), "station_mm": round(s), "power_mm": round(p)} for y, s, p in zip(years, season_s, season_p)]
    driest = lambda key: [r["season"] for r in sorted(seasons, key=lambda r: r[key])[:4]]
    return {"source": "inia_la_estanzuela", "period": [str(days[0]), str(days[-1])], "rain": rain, "temperature": temperature,
            "evapotranspiration": et, "seasons_dec_mar": seasons,
            "driest_seasons": {"station": driest("station_mm"), "power": driest("power_mm")},
            "location_note": "the station and the NASA point share the location; daily agreement is limited by the 0.5 x 0.625 degree grid cell"}
