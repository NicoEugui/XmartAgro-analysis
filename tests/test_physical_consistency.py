"""Physical and temporal consistency of the water scenarios: bounds, mass balance, continuity, auditability.
Run: python3 test_physical_consistency.py"""

import unittest
from xmart_analysis.engine import sensor_input as si
import fixtures
from datetime import date, timedelta

from xmart_analysis.engine import water_model as wm
from xmart_analysis.engine import water_scenarios as ws

TOLERANCE = 1e-9


class Fixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cal = wm.load_calibration()
        cls.params = [cal["parameters"][k] for k in wm.PARAMS]
        cls.weather = wm.load_power()
        cls.et0 = wm.precompute_et0(cls.weather)
        cls.theta0 = si.reading()["volumetric_moisture"]
        cls.initial_mm = si.to_available_water_mm(cls.theta0, cls.params)
        cls.out = fixtures.water_doc("en")


class PhysicalConsistency(Fixtures):
    def balance(self, year):
        start = date(year, *ws.START)
        end = start + timedelta(days=ws.HORIZON_DAYS)
        rows = wm.simulate_water_balance(self.params, self.weather, self.et0, start, end, self.initial_mm,
                                         lambda d: self.params[2])
        return start, rows

    def test_stored_water_stays_between_zero_and_capacity_in_every_season(self):
        capacity = self.params[1]
        for year in ws.SEASON_YEARS:
            _, rows = self.balance(year)
            for r in rows:
                self.assertGreaterEqual(r["water_mm"], -TOLERANCE, (year, r["day"]))
                self.assertLessEqual(r["water_mm"], capacity + TOLERANCE, (year, r["day"]))

    def test_inputs_and_outputs_close_the_balance_every_day(self):
        for year in ws.SEASON_YEARS:
            _, rows = self.balance(year)
            previous = self.initial_mm
            for r in rows:
                expected = previous + r["rain_mm"] - r["loss_mm"] - r["actual_mm"]
                self.assertAlmostEqual(r["water_mm"], expected, delta=1e-9, msg=(year, r["day"]))
                previous = r["water_mm"]

    def test_each_scenario_uses_one_continuous_climate_sequence(self):
        for year in ws.SEASON_YEARS:
            start, rows = self.balance(year)
            self.assertEqual(len(rows), ws.HORIZON_DAYS + 1)
            for i, r in enumerate(rows):
                self.assertEqual(r["day"], start + timedelta(days=i))  # consecutive calendar days
                self.assertEqual(r["rain_mm"], self.weather[r["day"]]["PRECTOTCORR"])  # that very day's rain

    def test_the_scenario_engine_matches_the_audited_balance(self):
        trajs = ws.trajectories(self.params, self.weather, self.et0, self.theta0)
        for year, (start, thetas) in trajs.items():
            _, rows = self.balance(year)
            for theta, r in zip(thetas, rows):
                self.assertAlmostEqual(theta, self.params[0] + r["water_mm"] / wm.ROOT_DEPTH_MM, delta=1e-9)


class Auditability(Fixtures):
    def test_percentiles_use_the_same_horizon_day_in_every_scenario(self):
        trajs = ws.trajectories(self.params, self.weather, self.et0, self.theta0)
        recomputed = {r["day"]: r for r in ws.spread(trajs, self.params)}
        for row in self.out["spread_by_day"]:
            again = recomputed[row["day"]]
            self.assertEqual(row["median_mm"], again["median_mm"])
            self.assertEqual(row["p10_mm"], again["p10_mm"])
            self.assertEqual(row["p90_mm"], again["p90_mm"])
        for t in (th for _, th in trajs.values()):
            self.assertEqual(len(t), ws.HORIZON_DAYS + 1)

    def test_every_scenario_keeps_its_historical_season_identity(self):
        index = self.out["scenario_index"]
        self.assertEqual(len(index), len(ws.SEASON_YEARS))
        self.assertEqual(len({r["season"] for r in index}), len(ws.SEASON_YEARS))
        for r, year in zip(index, ws.SEASON_YEARS):
            self.assertEqual(r["season"], ws.season_name(year))
            self.assertEqual(r["start_date"], str(date(year, *ws.START)))
            self.assertEqual(r["end_date"], str(date(year, *ws.START) + timedelta(days=ws.HORIZON_DAYS)))
            self.assertLessEqual(r["minimum_mm"], r["final_mm"])
            self.assertTrue(0 <= r["day_of_minimum"] <= ws.HORIZON_DAYS)

    def test_the_lowest_water_scenarios_come_from_the_index(self):
        by_minimum = sorted(self.out["scenario_index"], key=lambda r: r["minimum_mm"])[:5]
        self.assertEqual(self.out["lowest_water_scenarios"], [r["season"] for r in by_minimum])

    def test_the_driest_by_rain_scenarios_rank_the_rain_of_the_window_not_the_water_minimum(self):
        by_rain = sorted(self.out["scenario_index"], key=lambda r: r["rain_mm"])[:5]
        self.assertEqual(self.out["driest_by_rain_scenarios"], [r["season"] for r in by_rain])

    def test_the_rain_of_a_scenario_is_the_sum_of_its_window(self):
        weather = wm.load_power()
        row = self.out["scenario_index"][0]
        begin = date.fromisoformat(row["start_date"])
        total = sum(weather[begin + timedelta(days=i)]["PRECTOTCORR"] for i in range(ws.HORIZON_DAYS + 1))
        self.assertAlmostEqual(row["rain_mm"], total, places=1)

    def test_all_climate_days_exist_for_every_scenario(self):
        for year in ws.SEASON_YEARS:
            start = date(year, *ws.START)
            for i in range(ws.HORIZON_DAYS + 1):
                self.assertIn(start + timedelta(days=i), self.weather)


class Plausibility(Fixtures):
    def test_base_soil_is_plausible(self):
        self.assertEqual(ws.plausibility(self.params, self.theta0), [])

    def test_extreme_soils_are_rejected(self):
        wet = list(self.params)
        wet[1] = self.params[1] * 2.5
        self.assertIn("field_capacity_out_of_range", ws.plausibility(wet, self.theta0))
        dry = list(self.params)
        dry[0] = 0.30
        self.assertIn("sensor_below_wilting_point", ws.plausibility(dry, self.theta0))
        self.assertIn("wilting_point_out_of_range", ws.plausibility(dry, self.theta0))


if __name__ == "__main__":
    unittest.main()
