"""Shared test inputs: the demo answers and the water-scenario documents built in-process."""

import copy
import csv
from functools import lru_cache
from pathlib import Path

from xmart_analysis.engine import water_model as wm
from xmart_analysis.engine import water_scenarios as ws
from xmart_analysis.validation import smap
from xmart_analysis.engine.i18n import resolve

DEFAULT_ANSWERS = {
    "sensor": {"source": "simulated"},
    "reading_date": "11-14",
    "current_crop": {"crop": "soybean_1st", "sowing": "11-10"},
    "past_seasons": [
        {
            "season": "2025/26",
            "crops": ["barley", "soybean_2nd"],
            "rating": 2,
            "yield_kg_ha": None,
        },
        {
            "season": "2024/25",
            "crops": ["wheat", "soybean_2nd"],
            "rating": 3,
            "yield_kg_ha": None,
        },
        {
            "season": "2023/24",
            "crops": ["rapeseed", "soybean_2nd"],
            "rating": 4,
            "yield_kg_ha": None,
        },
        {"season": "2022/23", "crops": ["maize"], "rating": 1, "yield_kg_ha": None},
    ],
    "agronomist": {
        "analysis_date": "2026-05",
        "organic_matter_pct": 3.4,
        "phosphorus_ppm": 12,
        "ph": 5.8,
        "erosion_t_ha_yr": 6.2,
        "soil_type": "CONEAT 10.8b, Brunosol",
        "soil_type_confirmed": True,
    },
    "options": [
        {"kind": "crop", "crop": "soybean_1st", "sowing": "12-05"},
        {"kind": "crop", "crop": "maize_2nd", "sowing": "12-10"},
        {"kind": "crop", "crop": "sorghum_1st", "sowing": "10-17"},
    ],
}


def default_answers():
    return copy.deepcopy(DEFAULT_ANSWERS)


@lru_cache(maxsize=None)
def _water_scenarios():
    return ws.build_scenarios()


def water_doc(lang):
    return copy.deepcopy(resolve(_water_scenarios(), lang))


def write_synthetic_smap(root, ctx):
    """NASA-shaped SMAP L4 and L3 files built from the model itself (L4 plus a fixed wobble, L3 a scaled subsample)."""
    root = Path(root)
    start = smap.PERIODS["calibration"][0]
    truth = wm.simulate_moisture(ctx["params"], ctx["weather"], ctx["et0"], start, smap.PERIODS["validation"][1], 0.30)
    with open(root / "l4.csv", "w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Date", smap.L4_COLUMN])
        for d, v in truth.items():
            for _ in range(8):
                writer.writerow([d.isoformat(), v + 0.01 * ((d.toordinal() % 5) - 2) / 2])
    with open(root / "l3.csv", "w", newline="") as stream:
        writer = csv.writer(stream)
        am, qa, pm, qp = smap.L3_PAIRS[0] + smap.L3_PAIRS[1]
        writer.writerow(["Date", am, qa, pm, qp])
        for d, v in truth.items():
            if d.toordinal() % 3 == 0:
                writer.writerow([d.isoformat(), v * 0.9, 0, -9999, 7])
    return root / "l3.csv", root / "l4.csv"
