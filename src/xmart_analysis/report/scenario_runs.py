"""What the model says for a crop sown on a date: the engine's sowing scenarios over a grid of crops and dates, as one plain document.

Each run applies every complete historical season to the reading and the sowing date (`engine.sowing_scenarios.evaluate_sowing`); the counts
are seasons, not probabilities, and nothing here is a forecast or a recommendation.
"""

from datetime import date, timedelta

from xmart_analysis.engine import context as engine_context
from xmart_analysis.engine import crops_uy, deficit, sowing_scenarios

CROPS = ("soybean_1st", "soybean_2nd", "maize", "wheat", "barley")
SHIFTS_DAYS = (-30, -15, 0, 15, 30)
READINGS = (0.15, sowing_scenarios.si.SIMULATED_THETA, 0.40)
DETAIL_CROP = "soybean_1st"
MONTHS = {"en": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), "es": "ene feb mar abr may jun jul ago sep oct nov dic".split()}


def day_label(month_day, lang="en"):
    """'11-15' as '15 Nov' (a calendar day, no year: the same day is applied to every historical season)."""
    month, day = (int(x) for x in month_day.split("-"))
    return f"{day} {MONTHS[lang][month - 1]}"


def shifted(sowing, days):
    day = date(2001, *sowing) + timedelta(days=days)
    return (day.month, day.day)


def run(context=None):
    context = context or engine_context.build_context()
    kw = {k: context[k] for k in ("params", "weather", "et0")}

    def counts(doc):
        return {deficit.DROP_NAMES[c]: n for c, n in doc["season_counts"].items()}

    crops, detail, doc = {}, None, None
    for crop in CROPS:
        default = crops_uy.CROPS[crop]["sowing"]
        rows = []
        for shift in SHIFTS_DAYS:
            sowing = shifted(default, shift)
            doc = sowing_scenarios.evaluate_sowing(crop, sowing, **kw)
            rows.append({"sowing": doc["sowing"], "shift_days": shift, "first_sowing": doc["season_results"][0]["sowing_date"],
                         "last_sowing": doc["season_results"][-1]["sowing_date"], "seasons": doc["scenarios"], "counts": counts(doc),
                         "median_stress": doc["median_stress"], "median_water_at_sowing_mm": doc["median_water_at_sowing_mm"],
                         "warnings": [w["code"] for w in doc["warnings"]]})
            if crop == DETAIL_CROP and shift == 0:
                detail = {"crop": crop, "sowing": doc["sowing"], "seasons": [
                    {"season": r["season"], "sowing_date": r["sowing_date"], "water_at_sowing_mm": r["water_at_sowing_mm"], "stress": r["stress"],
                     "deficit_days": r["deficit_days"], "class": deficit.DROP_NAMES[r["class"]]} for r in doc["season_results"]]}
        crops[crop] = {"default_sowing": f"{default[0]:02d}-{default[1]:02d}", "dates": rows}
    reading = [{"volumetric_moisture": theta, "counts": counts(sowing_scenarios.evaluate_sowing(
        DETAIL_CROP, crops_uy.CROPS[DETAIL_CROP]["sowing"], reading_theta=theta, **kw))} for theta in READINGS]
    return {"reading_date": doc["reading"]["date"], "crops": crops, "detail": detail, "reading_sensitivity": {"crop": DETAIL_CROP, "readings": reading},
            "note": "counts are historical seasons applied to the reading, not probabilities; the reading is simulated and crop parameters are pending"}
