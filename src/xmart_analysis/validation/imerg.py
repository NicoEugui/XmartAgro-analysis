"""Is the NASA POWER rain the model runs on consistent with NASA GPM IMERG, an independent satellite estimate? (exploratory)

IMERG Final daily (GPM_3IMERGDF V07, 0.1 degree) as a Giovanni area-averaged time series CSV for the cell of the field, a NASA export
bundled in sites/<site>/imerg_daily.csv. POWER rain is MERRA-2 reanalysis; IMERG merges satellite microwave and infrared estimates with
gauge data, so agreement between them is a real check, and so is their disagreement. A 0.1 degree cell is a mean over about 10 km,
so daily agreement is limited.
"""

from collections import defaultdict
from datetime import date, timedelta

from ..engine import context as engine_context
from ..engine import water_scenarios as ws
from .files import check_coordinates
from .stats import pearson, spearman

WET_DAY_MM = 1.0
SEASON_DAYS = 121  # 1 December to 31 March
FILL = -9999.0


def load(path):
    """{date: mm/day}; fill values are dropped. The cell named in the header must be the site's point."""
    lines = open(path, encoding="utf-8").read().splitlines()
    box = next((l for l in lines if l.startswith("Data Bounding Box")), None)
    if box:
        west, south, east, north = (float(x) for x in box.split(":", 1)[1].lstrip(",").strip().strip('"').split(","))
        check_coordinates(path, (south + north) / 2, (west + east) / 2, tolerance=0.1)
    start = next(i for i, l in enumerate(lines) if l.startswith("time,")) + 1
    out = {}
    for line in lines[start:]:
        day, _, value = line.partition(",")
        if day and float(value) > FILL:
            out[date.fromisoformat(day[:10])] = float(value)
    return out


def season_rain(series, year):
    days = [date(year, 12, 1) + timedelta(days=i) for i in range(SEASON_DAYS)]
    return sum(series[d] for d in days) if all(d in series for d in days) else None


def run(path, context=None):
    context = context or engine_context.build_context()
    weather = context["weather"]
    imerg = load(path)
    days = [d for d in sorted(weather) if d in imerg]
    rain_i, rain_p = [imerg[d] for d in days], [weather[d]["PRECTOTCORR"] for d in days]
    monthly = defaultdict(lambda: [0.0, 0.0])
    for d, a, b in zip(days, rain_i, rain_p):
        monthly[(d.year, d.month)][0] += a
        monthly[(d.year, d.month)][1] += b
    month_i, month_p = zip(*monthly.values())
    cycle = [{"month": m, "imerg": round(sum(v[0] for k, v in monthly.items() if k[1] == m) / sum(k[1] == m for k in monthly), 1),
              "power": round(sum(v[1] for k, v in monthly.items() if k[1] == m) / sum(k[1] == m for k in monthly), 1)} for m in range(1, 13)]
    by_day_p = {d: weather[d]["PRECTOTCORR"] for d in days}
    seasons = []
    for year in ws.SEASON_YEARS:
        i, p = season_rain(imerg, year), season_rain(by_day_p, year)
        if i is not None and p is not None:
            seasons.append({"season": ws.season_name(year), "imerg_mm": round(i), "power_mm": round(p)})
    si, sp = [s["imerg_mm"] for s in seasons], [s["power_mm"] for s in seasons]
    driest = lambda key: [r["season"] for r in sorted(seasons, key=lambda r: r[key])[:4]]
    years = len(days) / 365.25
    return {"source": "gpm_imerg", "period": [str(days[0]), str(days[-1])], "days": len(days),
            "rain": {"daily_r": round(pearson(rain_i, rain_p), 3), "monthly_r": round(pearson(list(month_i), list(month_p)), 3),
                     "season_dec_mar_r": round(pearson(si, sp), 3), "season_dec_mar_rho": round(spearman(si, sp), 3),
                     "mean_annual_mm": {"imerg": round(sum(rain_i) / years), "power": round(sum(rain_p) / years)},
                     "wet_day_share": {"imerg": round(sum(v >= WET_DAY_MM for v in rain_i) / len(days), 3),
                                       "power": round(sum(v >= WET_DAY_MM for v in rain_p) / len(days), 3)}},
            "monthly_mean_mm": cycle, "seasons_dec_mar": seasons, "driest_seasons": {"imerg": driest("imerg_mm"), "power": driest("power_mm")},
            "note": "IMERG is a 0.1 degree satellite estimate: daily agreement is limited, totals are what the water balance needs"}
