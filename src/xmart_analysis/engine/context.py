"""Calibrated parameters and climate, built once and reused across evaluations."""

from . import water_model as wm


def build_context():
    params = [wm.load_calibration()["parameters"][k] for k in wm.PARAMS]
    weather = wm.load_power()
    return {"params": params, "weather": weather, "et0": wm.precompute_et0(weather)}
