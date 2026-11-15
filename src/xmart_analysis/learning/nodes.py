"""Sensor nodes of a field: each measures its own patch (depth and soil differ inside a field) with its own offset and noise.

A node's reading is only usable after a reference measurement (a soil sample weighed, dried and weighed again) tells how far
its probe is off; without it the node is stored but not used for learning, as the specification says.
"""

import random
from dataclasses import dataclass

from ..engine import sensor_series, tables
from ..engine import water_model as wm
from . import fields


@dataclass(frozen=True)
class Node:
    node_id: str
    field_id: str
    depth_cm: int
    capacity_factor: float
    theta_min_shift: float
    bias: float
    noise_sd: float


def of_field(field_id):
    return tuple(Node(r["node_id"], r["field_id"], int(r["depth_cm"]), float(r["capacity_factor"]), float(r["theta_min_shift"]),
                      float(r["bias"]), float(r["noise_sd"])) for r in tables.read("learning/nodes") if r["field_id"] == field_id)


def truth(node, field, context, window):
    params = sensor_series.truth_params(fields.soil(field, context["params"]), node.capacity_factor, node.theta_min_shift)
    return wm.simulate_moisture(params, context["weather"], context["et0"], *window, tables.constant("sensor_truth_start_theta"))


def readings(node, field, context, window):
    """{date: raw moisture} the node reports."""
    return sensor_series.observe(truth(node, field, context, window), window[0], node.bias, node.noise_sd, node.node_id)


def reference_offset(node):
    """The offset the reference measurement finds: the node's true offset plus the error of weighing a sample."""
    noise = random.Random(f"{tables.constant('learn_seed')}:reference:{node.node_id}")
    return node.bias + noise.gauss(0, tables.constant("learn_reference_noise_sd"))


def calibrated(node, raw):
    return {d: round(v - reference_offset(node), 4) for d, v in raw.items()}


def field_series(field, context, window):
    """{date: moisture} of the field: the mean of its calibrated nodes."""
    series = [calibrated(n, readings(n, field, context, window)) for n in of_field(field.field_id)]
    return {d: round(sum(s[d] for s in series) / len(series), 4) for d in series[0]}
