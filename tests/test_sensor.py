"""The sensor series and the model's correction by it: reproducible data, a hook that is neutral without readings, and a measured gain."""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from xmart_analysis.engine import context as engine_context
from xmart_analysis.engine import sensor_series, tables
from xmart_analysis.engine import water_model as wm
from xmart_analysis.engine.errors import EngineError
from xmart_analysis.validation import sensor_assimilation


class Correction(unittest.TestCase):
    PARAMS = [0.19, 160.0, 0.9, 0.7, 0.95, 0.27]

    def test_nudge_ignores_adopts_or_moves_part_of_the_way(self):
        self.assertEqual(wm.nudge(50.0, 80.0, 0.0), 50.0)
        self.assertEqual(wm.nudge(50.0, 80.0, 1.0), 80.0)
        self.assertAlmostEqual(wm.nudge(50.0, 80.0, 0.3), 59.0)

    def test_water_from_theta_is_clamped_between_empty_and_full(self):
        self.assertEqual(wm.water_from_theta(0.05, 0.19, 160.0), 0.0)
        self.assertEqual(wm.water_from_theta(0.9, 0.19, 160.0), 160.0)
        self.assertAlmostEqual(wm.water_from_theta(0.29, 0.19, 160.0), 100.0)

    def run_model(self, **kwargs):
        start, end = date(2020, 1, 1), date(2020, 1, 30)
        weather = {start + timedelta(days=i): {"PRECTOTCORR": 2.0 if i % 5 == 0 else 0.0} for i in range(30)}
        et0 = {day: 4.0 for day in weather}
        return start, wm.simulate_moisture(self.PARAMS, weather, et0, start, end, 0.30, **kwargs)

    def test_without_readings_or_with_zero_gain_the_run_is_open_loop(self):
        start, blind = self.run_model()
        _, ignored = self.run_model(observations={start + timedelta(days=3): 0.5}, gain=0.0)
        _, empty = self.run_model(observations={}, gain=1.0)
        self.assertEqual(blind, ignored)
        self.assertEqual(blind, empty)

    def test_a_reading_with_full_gain_sets_the_modelled_moisture_that_day(self):
        start, _ = self.run_model()
        day = start + timedelta(days=9)
        _, corrected = self.run_model(observations={day: 0.35}, gain=1.0)
        self.assertAlmostEqual(corrected[day], 0.35, places=9)


class Series(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = engine_context.build_context()
        cls.readings = sensor_series.readings(cls.context)

    def test_the_bundled_dataset_is_what_the_generator_writes(self):
        self.assertEqual(sensor_series.load(), self.readings)

    def test_the_series_is_the_last_year_of_the_climate_and_inside_the_possible_range(self):
        first, last = sensor_series.span(self.context["weather"])
        self.assertEqual(last, max(self.context["weather"]))
        self.assertEqual(sorted(self.readings), [first + timedelta(days=i) for i in range((last - first).days + 1)])
        self.assertTrue(all(0.0 <= v <= tables.constant("max_theta") for v in self.readings.values()))

    def test_the_model_does_not_receive_the_truth(self):
        truth = sensor_series.truth(self.context)
        self.assertNotEqual(self.readings, truth)
        self.assertNotEqual(sensor_series.truth_params(self.context["params"]), self.context["params"])

    def test_the_file_roundtrips_and_a_cadence_keeps_every_nth_reading(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "readings.csv"
            sensor_series.write(path, self.readings)
            self.assertEqual(sensor_series.load(path), self.readings)
        weekly = sensor_series.every(self.readings, 7)
        self.assertEqual(len(weekly), 53)
        self.assertEqual(min(weekly), min(self.readings))

    def test_an_impossible_reading_stops_the_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.csv"
            path.write_text("date,volumetric_moisture,sensor_id\n2025-01-01,0.95,x\n", encoding="utf-8")
            with self.assertRaises(EngineError):
                sensor_series.load(path)

    def test_the_dataset_is_listed_as_simulated_and_never_as_data(self):
        row = next(r for r in tables.manifest() if r["path"].endswith(sensor_series.SOURCE_FILE))
        self.assertEqual(row["kind"], tables.SIMULATED)
        entry = next(r for r in tables.provenance() if r["item"] == row["path"])
        self.assertEqual(entry["status"], "assumption")
        self.assertIn("simulated", entry["note"])


class Experiment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = sensor_assimilation.run()

    def test_a_daily_sensor_brings_the_model_closer_to_the_field(self):
        daily = self.doc["with_sensor"][0]
        self.assertLess(daily["rmse"], self.doc["open_loop"]["rmse"])
        self.assertLess(daily["first_days_rmse"], self.doc["open_loop"]["first_days_rmse"])

    def test_fewer_readings_help_less(self):
        errors = [r["rmse"] for r in self.doc["with_sensor"]]
        self.assertEqual(errors, sorted(errors))
        self.assertLess(errors[-1], self.doc["open_loop"]["rmse"])

    def test_the_document_says_it_is_simulated_and_is_reproducible(self):
        self.assertIn("simulated", self.doc["note"])
        self.assertEqual(sensor_assimilation.run(), self.doc)


if __name__ == "__main__":
    unittest.main()
