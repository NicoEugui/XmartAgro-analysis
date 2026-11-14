"""What-if matrix used by test_stress_scenarios: sensor readings, dates, horizons and sowing cases."""

import json

from xmart_analysis.engine import sowing_scenarios as sw
from xmart_analysis.engine import water_model as wm
from xmart_analysis.engine import water_scenarios as ws
from xmart_analysis.engine.errors import EngineError
from xmart_analysis.engine.i18n import resolve

VALID_READINGS = [0.10, 0.15, 0.19, 0.28, 0.35, 0.45, 0.60]
INVALID_READINGS = [None, float("nan"), -0.1, 0.9, "wet"]
START_DATES = [(1, 1), (2, 28), (2, 29), (6, 30), (11, 14), (12, 31)]
HORIZONS = [7, 30, 120, 300, 600]
SOWING_CASES = [
    ("soybean_1st", (11, 14)),
    ("soybean_1st", (11, 15)),
    ("soybean_1st", (12, 5)),
    ("soybean_1st", (1, 15)),
    ("soybean_1st", (2, 29)),
    ("rapeseed", (5, 1)),
    ("maize", (4, 1)),
]
INVALID_SOWING = [
    ("lotus", (11, 15)),
    ("soybean_1st", (13, 1)),
    ("soybean_1st", (2, 30)),
    ("soybean_1st", "tomorrow"),
    ("sunflower", (11, 15)),
]


def record(group, name, fn, expect_error=False):
    """Run fn; classify the outcome as ok, rejected_as_expected or unexpected_break."""
    try:
        result = fn()
    except EngineError as exc:  # a structured, deliberate rejection
        status = "rejected_as_expected" if expect_error else "unexpected_rejection"
        return {
            "group": group,
            "scenario": name,
            "status": status,
            "message": str(exc)[:160],
            "error": exc.to_dict(),
        }
    except (
        ValueError
    ) as exc:  # a deliberate rejection that is not structured yet: not acceptable for the frontend
        return {
            "group": group,
            "scenario": name,
            "status": "unstructured_rejection",
            "message": str(exc)[:160],
        }
    except Exception as exc:  # noqa: BLE001 - anything else is a break we want to see
        return {
            "group": group,
            "scenario": name,
            "status": "unexpected_break",
            "message": f"{type(exc).__name__}: {str(exc)[:140]}",
        }
    status = "expected_error_not_raised" if expect_error else "ok"
    return {"group": group, "scenario": name, "status": status, "result": result}


def scenario_summary(doc):
    band = {r["day"]: r for r in doc["spread_by_day"]}
    day = 28 if 28 in band else max(band)
    values = [
        r[k] for r in doc["spread_by_day"] for k in ("p10_mm", "median_mm", "p90_mm")
    ]
    capacity = doc["initial_state"]["capacity_mm"]
    return {
        "initial_water_mm": doc["initial_state"]["water_levels"][
            "scenario_initial_water"
        ]["value"],
        "warnings": [w["code"] for w in doc["initial_state"]["reading_warnings"]],
        "scenarios": doc["scenarios"],
        "seasons_skipped": len(doc["seasons_skipped"]),
        "median_mm_at_day": {str(day): band[day]["median_mm"]},
        "within_bounds": all(-1e-9 <= v <= capacity + 1e-9 for v in values),
        "plausible_soils": doc["structural_sensitivity"]["plausible_configurations"],
        "structural_status": doc["structural_sensitivity"]["status"],
    }


def run_matrix():
    ctx_params = wm.load_calibration()
    params = [ctx_params["parameters"][k] for k in wm.PARAMS]
    weather = wm.load_power()
    et0 = wm.precompute_et0(weather)
    kw = {"params": params, "weather": weather, "et0": et0}
    rows = []
    for theta in VALID_READINGS:
        rows.append(
            record(
                "sensor_reading",
                f"theta={theta}",
                lambda t=theta: scenario_summary(ws.build_scenarios(t, **kw)),
            )
        )
    for theta in INVALID_READINGS:
        rows.append(
            record(
                "sensor_reading_invalid",
                f"theta={theta!r}",
                lambda t=theta: ws.build_scenarios(t, **kw),
                expect_error=True,
            )
        )
    for start in START_DATES:
        rows.append(
            record(
                "reading_date",
                f"start={start}",
                lambda s=start: scenario_summary(
                    ws.build_scenarios(0.28, start=s, **kw)
                ),
            )
        )
    for horizon in HORIZONS:
        rows.append(
            record(
                "horizon",
                f"horizon={horizon}",
                lambda h=horizon: scenario_summary(
                    ws.build_scenarios(0.28, horizon=h, **kw)
                ),
            )
        )
    rows.append(
        record(
            "horizon_invalid",
            "horizon=3",
            lambda: ws.build_scenarios(0.28, horizon=3, **kw),
            expect_error=True,
        )
    )
    rows.append(
        record(
            "horizon_invalid",
            "horizon=5000",
            lambda: ws.build_scenarios(0.28, horizon=5000, **kw),
            expect_error=True,
        )
    )

    for crop, sowing in SOWING_CASES:

        def run(c=crop, d=sowing):
            doc = sw.evaluate_sowing(c, d, **kw)
            return {
                "scenarios": doc["scenarios"],
                "season_counts": doc["season_counts"],
                "median_water_at_sowing_mm": doc["median_water_at_sowing_mm"],
                "median_stress": doc["median_stress"],
                "warnings": [w["code"] for w in doc["warnings"]],
                "counts_add_up": sum(doc["season_counts"].values()) == doc["scenarios"],
            }

        rows.append(record("sowing_date", f"{crop} sown {sowing}", run))
    for crop, sowing in INVALID_SOWING:
        rows.append(
            record(
                "sowing_date_invalid",
                f"{crop} sown {sowing!r}",
                lambda c=crop, d=sowing: sw.evaluate_sowing(c, d, **kw),
                expect_error=True,
            )
        )
    # Determinism: the same inputs give identical documents.
    first = json.dumps(resolve(ws.build_scenarios(0.28, **kw), "en"), sort_keys=True)
    second = json.dumps(resolve(ws.build_scenarios(0.28, **kw), "en"), sort_keys=True)
    rows.append(
        record(
            "determinism", "same inputs twice", lambda: {"identical": first == second}
        )
    )
    return rows
