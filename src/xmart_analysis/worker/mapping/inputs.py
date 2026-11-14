"""Backend documents (free text, ISO dates) to the closed answers the engine accepts."""

import re
import unicodedata
from datetime import datetime

from xmart_analysis.engine import platform_session as ps

CROP_NAMES = {
    "soja": "soybean_1st", "soja de primera": "soybean_1st", "soja de segunda": "soybean_2nd",
    "maiz": "maize", "maiz de primera": "maize", "maiz de segunda": "maize_2nd",
    "sorgo": "sorghum_1st", "sorgo de primera": "sorghum_1st", "sorgo de segunda": "sorghum_2nd",
    "trigo": "wheat", "cebada": "barley", "colza": "rapeseed", "canola": "rapeseed",
    "avena": "oat_cover", "avena de cobertura": "oat_cover", "lotus": "lotus", "trebol rojo": "red_clover",
    "pradera": "pasture_mix", "pastura": "pasture_mix", "girasol": "sunflower", "carinata": "carinata",
    "vicia": "vetch", "alfalfa": "alfalfa", "barbecho": "fallow",
}
SPLIT_RE = re.compile(r"\s*(?:\+|,|;|/| y )\s*")


def normalize(text):
    plain = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", plain.strip().lower())


def crop_id(text):
    key = normalize(text)
    if key in ps.HISTORY_CROP_CHOICES:
        return key
    return CROP_NAMES.get(key)


def crop_ids(text, notes, field):
    ids = []
    for part in SPLIT_RE.split(str(text or "")):
        if not part.strip():
            continue
        found = crop_id(part)
        if found:
            ids.append(found)
        else:
            notes.append({"code": "unknown_crop_name", "field": field, "received": part.strip()})
    return ids


def sowing_day(value, notes, field):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value)[:10])
    except ValueError:
        notes.append({"code": "invalid_date", "field": field, "received": str(value)})
        return None
    return f"{parsed.month:02d}-{parsed.day:02d}"


def current_crop(farmer, notes):
    crop = crop_ids(farmer.get("crop"), notes, "farmer.crop")
    sowing = sowing_day(farmer.get("sowing_date"), notes, "farmer.sowing_date")
    if not crop or not sowing:
        return None
    return {"crop": crop[0], "sowing": sowing}


def past_seasons(farmer, notes):
    out = []
    for i, season in enumerate(farmer.get("seasons") or []):
        name = season.get("season")
        if name not in ps.SEASON_CHOICES:
            notes.append({"code": "unknown_season", "field": f"farmer.seasons[{i}].season", "received": name})
            continue
        out.append({"season": name, "crops": crop_ids(season.get("crop"), notes, f"farmer.seasons[{i}].crop"),
                    "rating": season.get("rating"), "yield_kg_ha": season.get("yield_kg_ha")})
    return out


def agronomist(data):
    test = data.get("soil_test") or {}
    soil = data.get("soil_type") or {}
    name = ", ".join(x for x in (f"CONEAT {soil['coneat']}" if soil.get("coneat") else "", soil.get("name") or "") if x)
    return {"analysis_date": test.get("date"), "organic_matter_pct": test.get("om_pct"),
            "phosphorus_ppm": test.get("p_bray_ppm"), "ph": test.get("ph"),
            "erosion_t_ha_yr": data.get("erosion_t_ha_yr"), "soil_type": name or None,
            "soil_type_confirmed": bool(soil.get("confirmed"))}


def to_answers(inputs, reading, comparison):
    """Returns (answers, notes). Unreadable free text is dropped and reported, never guessed."""
    notes = []
    inputs = inputs or {}
    farmer = inputs.get("farmer") or {}
    answers = {"sensor": {"source": "manual", "moisture": reading.moisture},
               "reading_date": f"{reading.received_at.month:02d}-{reading.received_at.day:02d}",
               "past_seasons": past_seasons(farmer, notes), "agronomist": agronomist(inputs.get("agronomist") or {}),
               "options": [dict(o) for o in comparison]}
    current = current_crop(farmer, notes)
    if current:
        answers["current_crop"] = current
    return answers, tuple(notes)
