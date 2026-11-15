"""The simulated season of a field: what the model computes, what the field really lived and how the producer rated it.

The pipeline's stress uses the table's crop and the model's soil. The outcome uses the producer's variant of the crop and the
field's real soil, then Ky (FAO-33) turns that stress into a relative yield, noise adds what water does not explain, and the
producer's own scale turns the yield into the five ratings of the app. Model A has to learn how far the first predicts the last.
"""

import random

from ..engine import crops_uy as cu
from ..engine import tables
from ..engine import water_scenarios as ws
from . import fields, ndvi, producers, season

SOURCE = "simulated_panel"
RATINGS = ("very_bad", "bad", "good", "very_good", "excellent")
CLASS_OF_RATING = ("bad", "bad", "normal", "good", "good")  # the three classes model A predicts


def rating(relative_yield, bias=0.0):
    """1 (very bad) to 5 (excellent) from a relative yield and the producer's scale."""
    return 1 + sum(relative_yield + bias >= cut for cut in tables.constant("learn_rating_cuts"))


def record(field, context, crop, year, producer=None):
    """One simulated season of a field (a plain dict), or None if the climate record does not cover it."""
    rng = random.Random(f"{tables.constant('learn_seed')}:season:{field.field_id}:{producer.producer_id if producer else '-'}:{crop}:{year}")
    base = {"source": SOURCE, "simulated": True, "field_id": field.field_id, "producer_id": producer.producer_id if producer else None,
            "crop": crop, "season": ws.season_name(year), "year": year}
    if crop == producers.FALLOW:
        series = ndvi.curve(year, None, None, None, 0.0, 0.0, rng)
        return {**base, "sowing_date": None, "model_stress": None, "truth_stress": None, "relative_yield": None, "rating": None,
                "ndvi": ndvi.summary(series)}
    sowing = producers.sowing_date(crop, year, producer)
    variant = producers.crop_variant(crop, producer)
    model = season.stress(context["params"], cu.CROPS[crop], crop, sowing, context["weather"], context["et0"])
    real = season.stress(fields.soil(field, context["params"]), variant, crop, sowing, context["weather"], context["et0"])
    if model is None or real is None:
        return None
    limits = producers.crop_ranges()[crop]
    relative = 1 - limits["ky"] * real + rng.gauss(0, tables.constant("learn_yield_noise_sd"))
    series = ndvi.curve(year, crop, sowing, variant, real, limits["ndvi_peak"], rng)
    return {**base, "sowing_date": str(sowing), "model_stress": round(model, 4), "truth_stress": round(real, 4),
            "relative_yield": round(relative, 4), "rating": rating(relative, producer.rating_bias if producer else 0.0),
            "ndvi": ndvi.summary(series)}
