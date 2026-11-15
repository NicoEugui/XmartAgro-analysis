"""What the panel's simulated soils take from a soil unit: a texture class, a water-capacity factor and the satellite's planted error.

The unit is real (a coordinate's CONEAT group), what is made of it is a stated assumption: the texture class is the heaviest of the first two
soil orders named in the unit, the capacity factor grows with the unit's productivity index (the index sums up what the soil can produce, water
included), and the satellite error depends on the texture. Without a soil system every field falls back to a medium soil with no change in capacity.
"""

import random

from ..engine import tables

MEDIUM = 1


def _texture_of_orders():
    return {r["order"]: int(r["texture"]) for r in tables.read("soil_order_texture")}


def texture_class(unit):
    """0 light, 1 medium, 2 heavy: the heaviest of the first two soil orders of the unit (medium if there is no unit or no orders)."""
    if unit is None or not unit.dominant_orders:
        return MEDIUM
    texture = _texture_of_orders()
    return max(texture.get(order, MEDIUM) for order in unit.dominant_orders[:2])


def capacity_factor(unit):
    """How much water the field's soil holds against the soil the model was calibrated with: 1 at the middle index, straight lines to the ends."""
    if unit is None or unit.productivity_index is None:
        return 1.0
    low, mid, high = (tables.constant(f"soil_index_{k}") for k in ("low", "mid", "high"))
    low_factor, high_factor = tables.constant("soil_capacity_low"), tables.constant("soil_capacity_high")
    index = min(high, max(low, unit.productivity_index))
    if index <= mid:
        return low_factor + (1.0 - low_factor) * (index - low) / (mid - low)
    return 1.0 + (high_factor - 1.0) * (index - mid) / (high - mid)


def satellite_error(texture, field_id):
    """(offset, scale) planted in a simulated field's satellite: its texture class's, plus a small deterministic stray of the field's own."""
    rng = random.Random(f"{tables.constant('learn_seed')}:satellite:{field_id}")
    offset = tables.constant("learn_smap_offset_by_texture")[texture] + rng.uniform(-1, 1) * tables.constant("learn_smap_offset_jitter")
    scale = tables.constant("learn_smap_scale_by_texture")[texture] + rng.uniform(-1, 1) * tables.constant("learn_smap_scale_jitter")
    return round(offset, 4), round(scale, 4)
