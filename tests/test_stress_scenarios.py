"""Stress tests: changed sensor readings, dates, horizons, soils, rotations and crops must not break the engine,
must keep the invariants and must reject invalid input with a clear message. Run: python3 test_stress_scenarios.py"""

import scenario_matrix as sm
import unittest
from xmart_analysis.engine import context
from xmart_analysis.engine import water_model as wm
from xmart_analysis.engine import water_scenarios as ws


class Matrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cal = wm.load_calibration()
        cls.params = [cal["parameters"][k] for k in wm.PARAMS]
        cls.weather = wm.load_power()
        cls.et0 = wm.precompute_et0(cls.weather)
        cls.kw = {"params": cls.params, "weather": cls.weather, "et0": cls.et0}
        cls.rows = sm.run_matrix()
        cls.context = context.build_context()

    def by(self, group):
        return [r for r in self.rows if r["group"] == group]

    def test_nothing_breaks_unexpectedly(self):
        bad = [r for r in self.rows if r["status"] not in ("ok", "rejected_as_expected")]
        self.assertEqual(bad, [], bad)

    def test_valid_inputs_run_and_invalid_inputs_are_rejected(self):
        for group in ("sensor_reading", "reading_date", "horizon", "determinism"):
            for r in self.by(group):
                self.assertEqual(r["status"], "ok", r)
        for group in ("sensor_reading_invalid", "horizon_invalid", "unsupported_crop", "rotation_invalid"):
            for r in self.by(group):
                self.assertEqual(r["status"], "rejected_as_expected", r)
                self.assertTrue(r["message"])

    def test_water_stays_within_zero_and_capacity_for_every_scenario_run(self):
        for group in ("sensor_reading", "reading_date", "horizon"):
            for r in self.by(group):
                self.assertTrue(r["result"]["within_bounds"], r)

    def test_a_wetter_sensor_never_means_less_water_or_more_stress_scenarios(self):
        docs = [ws.build_scenarios(t, **self.kw) for t in (0.19, 0.28, 0.35, 0.45)]
        initial = [d["initial_state"]["water_levels"]["scenario_initial_water"]["value"] for d in docs]
        self.assertEqual(initial, sorted(initial))
        for day in (7, 28, 56):
            medians = [next(r for r in d["spread_by_day"] if r["day"] == day)["median_mm"] for d in docs]
            self.assertEqual(medians, sorted(medians), day)
        below = [d["scenarios_below_threshold_by_day"]["30"] for d in docs]
        self.assertEqual(below, sorted(below, reverse=True))

    def test_readings_outside_the_assumed_soil_are_flagged_not_hidden(self):
        codes = {r["scenario"]: r["result"]["warnings"] for r in self.by("sensor_reading")}
        self.assertIn("below_assumed_wilting_point", codes["theta=0.1"])
        self.assertIn("above_assumed_field_capacity", codes["theta=0.45"])
        self.assertEqual(codes["theta=0.28"], [])

    def test_a_dry_sensor_with_no_plausible_soil_is_reported_not_a_crash(self):
        doc = ws.build_scenarios(0.10, **self.kw)
        ss = doc["structural_sensitivity"]
        self.assertEqual(ss["status"], "no_plausible_configuration")
        self.assertIsNone(ss["envelope_by_day_m3_m3"])
        self.assertEqual(ss["plausible_configurations"], 0)

    def test_leap_day_and_year_end_dates_work(self):
        for start in ((2, 29), (12, 31), (1, 1)):
            doc = ws.build_scenarios(0.28, start=start, **self.kw)
            self.assertEqual(doc["scenarios"], len(ws.SEASON_YEARS))
        leap = ws.safe_date(2023, 2, 29)
        self.assertEqual((leap.month, leap.day), (2, 28))

    def test_a_horizon_beyond_the_record_skips_and_reports_seasons(self):
        doc = ws.build_scenarios(0.28, horizon=400, **self.kw)
        self.assertLess(doc["scenarios"], len(ws.SEASON_YEARS))
        self.assertEqual(doc["scenarios"] + len(doc["seasons_skipped"]), len(ws.SEASON_YEARS))
        self.assertEqual(doc["seasons_skipped"][0]["reason"], "window_outside_climate_record")





if __name__ == "__main__":
    unittest.main()
