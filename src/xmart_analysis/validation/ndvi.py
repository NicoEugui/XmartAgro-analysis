"""Does vegetation activity seen by MODIS fall in the seasons the model finds most stressed? (exploratory)

MODIS MOD13Q1 NDVI, 250 m pixel at the site (a NASA export, bundled in sites/<site>/modis_ndvi.csv). The pixel mixes crops, stubble and
pasture and what was in the field each year is unknown, so NDVI describes the pixel, not a rotation; low NDVI is not bare soil.
Only composites of good quality are used. Per season: mean NDVI from December to March against the modelled critical-stage stress.
"""

import csv
import statistics
from datetime import date

from ..engine import context as engine_context
from ..engine import crops_uy as cu
from . import survey
from .files import check_point
from .stats import permutation_p, spearman

FIRST_SEASON = 2002  # MODIS composites start in 2000; the first full December-March window is 2002/03
MIN_COMPOSITES = 6
TOP = 6
LIMITATIONS = ["the pixel mixes crops, stubble and pasture; what was in the field each year is unknown",
               "a high NDVI does not prove healthy soil", "250 m resolution"]


def load(path):
    """[(date, NDVI)] of the composites with pixel reliability 0 (good quality)."""
    check_point(path)
    column = lambda row, suffix: next(v for k, v in row.items() if k.endswith(suffix))  # noqa: E731
    with open(path, newline="") as stream:
        return [(date.fromisoformat(r["Date"][:10]), float(column(r, "16_days_NDVI")))
                for r in csv.DictReader(stream) if float(column(r, "pixel_reliability")) == 0]


def run(path, context=None):
    context = context or engine_context.build_context()
    series = load(path)
    stress = {crop: survey.season_stress(crop, context) for crop in survey.CROPS if crop in cu.CROPS}
    rows = []
    for year in range(FIRST_SEASON, max(d.year for d, _ in series)):
        values = [v for d, v in series if date(year, 12, 1) <= d <= date(year + 1, 3, 31)]
        season = f"{year}/{(year + 1) % 100:02d}"
        if len(values) >= MIN_COMPOSITES and all(season in s for s in stress.values()):
            rows.append({"season": season, "ndvi_dec_mar": round(statistics.mean(values), 3),
                         **{f"{crop}_stress": s[season] for crop, s in stress.items()}})
    ndvi = [r["ndvi_dec_mar"] for r in rows]
    correlations = {}
    for crop in stress:
        values = [r[f"{crop}_stress"] for r in rows]
        correlations[crop] = {"spearman_ndvi_vs_minus_stress": round(-spearman(ndvi, values), 3),
                              "permutation_p": round(permutation_p(ndvi, [-v for v in values]), 4)}
    lowest = {r["season"] for r in sorted(rows, key=lambda r: r["ndvi_dec_mar"])[:TOP]}
    stressed = {r["season"] for r in sorted(rows, key=lambda r: -r[f"{survey.CROPS[0]}_stress"])[:TOP]}
    return {"source": "modis_ndvi", "good_composites": len(series), "seasons": rows, "correlations": correlations,
            "lowest_ndvi_seasons": sorted(lowest), "most_stressed_seasons": sorted(stressed),
            "overlap": len(lowest & stressed), "overlap_expected_by_chance": round(TOP * TOP / len(rows), 1),
            "limitations": LIMITATIONS}
