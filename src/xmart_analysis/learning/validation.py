"""Validation with whole fields kept apart: the question is whether a model works for a field it has never seen."""

import random

import numpy as np

from ..engine import tables


def holdout(make, rows, share=None, rounds=None):
    """Mean and spread of every metric over `rounds` random splits that keep `share` of the fields out of training.

    `make` builds a fresh model. Rows with the same `field_id` always fall on the same side of a split."""
    share = tables.constant("learn_holdout_share") if share is None else share
    rounds = tables.constant("learn_holdout_rounds") if rounds is None else rounds
    fields = sorted({r["field_id"] for r in rows})
    kept = max(1, round(len(fields) * share))
    rng = random.Random(tables.constant("learn_seed"))
    collected = {}
    for _ in range(rounds):
        apart = set(rng.sample(fields, kept))
        model = make().fit([r for r in rows if r["field_id"] not in apart])
        for key, value in model.metrics([r for r in rows if r["field_id"] in apart]).items():
            collected.setdefault(key, []).append(value)
    return {"rounds": rounds, "fields_apart": kept, "fields": len(fields),
            "metrics": {k: {"mean": float(np.mean(v)), "sd": float(np.std(v))} for k, v in collected.items()}}
