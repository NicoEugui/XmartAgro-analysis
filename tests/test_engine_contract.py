"""Engine contract tests: structured errors for the frontend and behaviour on inconsistent data.
Run: python3 test_engine_contract.py"""
import unittest
from datetime import date

from xmart_analysis.engine import crops_uy as cu
from xmart_analysis.engine import sensor_input as si
from xmart_analysis.engine import sowing_scenarios as sw
from xmart_analysis.engine import water_model as wm
from xmart_analysis.engine import water_scenarios as ws
from xmart_analysis.engine.errors import EngineError, call


def code_of(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except EngineError as exc:
        return exc.code
    return None


class Fixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cal = wm.load_calibration()
        cls.params = [cal["parameters"][k] for k in wm.PARAMS]
        cls.weather = wm.load_power()
        cls.et0 = wm.precompute_et0(cls.weather)
        cls.kw = {"params": cls.params, "weather": cls.weather, "et0": cls.et0}


class StructuredErrors(Fixtures):
    def test_every_rejection_has_a_code_a_field_and_a_message(self):
        cases = [lambda: ws.build_scenarios(None, **self.kw), lambda: ws.build_scenarios(0.9, **self.kw),
                 lambda: ws.build_scenarios(0.28, horizon=3, **self.kw),
                 lambda: ws.build_scenarios(0.28, start=(13, 1), **self.kw),
                 lambda: cu.require_crop("sunflower"),
                 lambda: sw.evaluate_sowing("lotus", (11, 15), **self.kw)]
        for case in cases:
            with self.assertRaises(EngineError) as ctx:
                case()
            d = ctx.exception.to_dict()
            self.assertTrue(d["code"] and d["message"] and "field" in d and isinstance(d["details"], dict), d)

    def test_codes_are_stable(self):
        self.assertEqual(code_of(si.validate_theta, None), "invalid_moisture")
        self.assertEqual(code_of(si.validate_theta, float("nan")), "invalid_moisture")
        self.assertEqual(code_of(si.validate_theta, -0.1), "moisture_out_of_range")
        self.assertEqual(code_of(ws.build_scenarios, 0.28, horizon=3, **self.kw), "horizon_out_of_range")
        self.assertEqual(code_of(ws.build_scenarios, 0.28, horizon=True, **self.kw), "horizon_out_of_range")
        self.assertEqual(code_of(ws.build_scenarios, 0.28, start=(2, 30), **self.kw), "invalid_date")
        self.assertEqual(code_of(cu.require_crop, "nonsense"), "unsupported_crop")
        self.assertEqual(code_of(sw.evaluate_sowing, "lotus", (11, 15), **self.kw), "perennial_crop_has_no_sowing_date")
        self.assertEqual(code_of(sw.evaluate_sowing, "soybean_1st", (13, 1), **self.kw), "invalid_date")

    def test_unsupported_crop_lists_what_is_supported(self):
        try:
            cu.require_crop("sunflower")
        except EngineError as exc:
            self.assertIn("rapeseed", exc.details["supported"])
            self.assertTrue(exc.details["pending_sources"])

    def test_call_never_raises_and_wraps_unexpected_failures(self):
        ok = call(ws.build_scenarios, 0.28, **self.kw)
        self.assertTrue(ok["ok"] and ok["result"]["scenarios"] == len(ws.SEASON_YEARS))
        bad = call(ws.build_scenarios, None, **self.kw)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["error"]["code"], "invalid_moisture")
        unexpected = call(lambda: {}["missing"])
        self.assertFalse(unexpected["ok"])
        self.assertEqual(unexpected["error"]["code"], "internal_error")
        self.assertEqual(unexpected["error"]["details"]["type"], "KeyError")


class InconsistentClimateData(Fixtures):
    def modified(self, change):
        weather = {d: dict(v) for d, v in self.weather.items()}
        change(weather)
        return weather

    def test_negative_rain_is_rejected(self):
        weather = self.modified(lambda w: w[date(2000, 1, 5)].update(PRECTOTCORR=-3.0))
        self.assertEqual(code_of(ws.build_scenarios, 0.28, params=self.params, weather=weather), "invalid_climate_data")

    def test_minimum_temperature_above_maximum_is_rejected(self):
        weather = self.modified(lambda w: w[date(2000, 1, 5)].update(T2M_MIN=40.0, T2M_MAX=10.0))
        self.assertEqual(code_of(sw.evaluate_sowing, "soybean_1st", (11, 15), params=self.params, weather=weather),
                         "invalid_climate_data")

    def test_nan_and_missing_fields_are_rejected(self):
        weather = self.modified(lambda w: w[date(2000, 1, 5)].update(T2M=float("nan")))
        self.assertEqual(code_of(wm.validate_weather, weather), "invalid_climate_data")
        weather = self.modified(lambda w: w[date(2000, 1, 5)].pop("T2M_MAX"))
        self.assertEqual(code_of(wm.validate_weather, weather), "invalid_climate_data")
        self.assertEqual(code_of(wm.validate_weather, {}), "invalid_climate_data")

    def test_a_gap_in_the_record_skips_only_the_affected_seasons(self):
        gap = date(1995, 12, 20)  # inside the 1995 window that starts on 14 November
        weather = self.modified(lambda w: w.pop(gap))
        doc = ws.build_scenarios(0.28, params=self.params, weather=weather)
        skipped = {s["season"] for s in doc["seasons_skipped"]}
        self.assertIn("1995/96", skipped)
        self.assertEqual(doc["scenarios"], len(ws.SEASON_YEARS) - 1)
        self.assertNotIn("1995/96", {r["season"] for r in doc["scenario_index"]})

    def test_a_record_too_short_for_every_season_is_a_structured_error(self):
        short = {d: v for d, v in self.weather.items() if d < date(ws.SEASON_YEARS[0], 12, 31)}
        self.assertEqual(code_of(ws.build_scenarios, 0.28, params=self.params, weather=short), "no_complete_season")


class ScopeHonesty(Fixtures):

    def test_drainage_onset_is_not_called_field_capacity(self):
        self.assertIn("drainage_onset_fraction", wm.PARAMS)
        self.assertNotIn("field_capacity_fraction", wm.PARAMS)
        params = list(self.params)
        field_capacity = params[0] + params[1] / wm.ROOT_DEPTH_MM  # physical: bucket full = wilting + capacity
        onset_theta = params[0] + params[wm.PARAMS.index("drainage_onset_fraction")] * params[1] / wm.ROOT_DEPTH_MM
        self.assertLess(onset_theta, field_capacity)  # a separate, lower operational threshold
        self.assertEqual(ws.plausibility(params, 0.28), [])


if __name__ == "__main__":
    unittest.main()
