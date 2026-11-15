"""The twelve producers of the panel: whose field, which crops in which years and how their crops differ from the table.

The survey gives each producer's rotation in written order but no years, so the simulation assigns them: the producer's crops are
cycled over the last `learn_panel_seasons` seasons from a producer-specific starting point. A crop the model does not cover
(pasture, vetch, cover crop) is a season of fallow. Each producer grows a variant of the table's crop: stages stretched, Kc and
p within the published range, sown a few days earlier or later.
"""

from dataclasses import dataclass
from datetime import timedelta

from ..engine import crops_uy as cu
from ..engine import rotations, tables
from ..engine import water_scenarios as ws

FALLOW = "fallow"


@dataclass(frozen=True)
class Producer:
    producer_id: str
    respondent: int
    field_id: str
    sowing_shift_days: int
    stage_scale: float
    kc_scale: float
    p_shift: float
    rating_bias: float


def all_producers():
    return tuple(Producer(r["producer_id"], int(r["respondent"]), r["field_id"], int(r["sowing_shift_days"]), float(r["stage_scale"]),
                          float(r["kc_scale"]), float(r["p_shift"]), float(r["rating_bias"])) for r in tables.read("learning/producers"))


def crop_ranges():
    return {r["crop"]: {k: (float(v) if k not in ("crop", "ky_status", "source_ref", "note") else v) for k, v in r.items()}
            for r in tables.read("learning/crop_ranges")}


def crop_variant(crop, producer=None):
    """The crop's parameters as this producer grows it (the table's own without a producer): stages, Kc mid and p adjusted."""
    base, limits = cu.CROPS[crop], crop_ranges()[crop]
    if producer is None:
        return dict(base)
    kc_mid = min(limits["kc_mid_max"] * 1.05, max(limits["kc_mid_min"] * 0.95, base["kc"][1] * producer.kc_scale))
    return {**base, "stages": tuple(max(1, round(d * producer.stage_scale)) for d in base["stages"]),
            "kc": (base["kc"][0], kc_mid, base["kc"][2]), "p": min(0.8, max(0.1, base["p"] + producer.p_shift))}


def sowing_date(crop, year, producer=None):
    month, day = cu.CROPS[crop]["sowing"]
    return ws.safe_date(year, month, day) + timedelta(days=producer.sowing_shift_days if producer else 0)


def crop_sequence(respondent, full=False):
    """The respondent's crops in written order (FALLOW for what the model does not cover); a respondent who wrote no rotation gets
    the crops every surveyed producer wrote. With `full` every crop the producer wrote keeps its name (pasture, vetch, cover crop...), as
    the soil needs it; a name the soil rules do not know is FALLOW."""
    known = tables.survey_rotations()
    asked = [respondent] if respondent in known else sorted(known)
    if full:
        effects = tables.soil_effects()
        names = (e["engine_crop"] or e["survey_crop"] for r in asked for e in rotations.entries(r))
        return [n if n in effects else FALLOW for n in names]
    return [e["engine_crop"] if e["status"] == "modelled" and e["engine_crop"] in crop_ranges() else FALLOW
            for r in asked for e in rotations.entries(r)]


def seasons(producer, full=False):
    """[(year, crop or FALLOW)] of the producer's last seasons (`full`: every crop written, see `crop_sequence`)."""
    sequence = crop_sequence(producer.respondent, full)
    last, count = tables.constant("history_last_season_year"), tables.constant("learn_panel_seasons")
    return [(last - count + 1 + i, sequence[(producer.respondent + i) % len(sequence)]) for i in range(count)]
