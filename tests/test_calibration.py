"""Calibration: the shipped parameters match the corrected demand, stay in plausible soils and the fit command runs."""
import importlib.util
import tempfile
import unittest

import fixtures
from xmart_analysis import calibration
from xmart_analysis.engine import context, tables
from xmart_analysis.engine import water_model as wm
from xmart_analysis.validation import station

HAVE_SCIPY = importlib.util.find_spec("scipy") is not None


class ShippedCalibration(unittest.TestCase):
    def test_it_records_the_point_and_the_demand_it_was_fitted_with(self):
        fit = tables.calibration()
        self.assertEqual(set(fit["point"]), {"latitude", "longitude"})
        self.assertIn("et0_scale", fit)

    def test_the_scale_is_what_the_station_gives(self):
        fitted = station.fit_et0_scale(context.build_context()["weather"])
        self.assertAlmostEqual(tables.constant("et0_scale"), fitted, delta=5e-4)

    def test_the_default_demand_is_the_scaled_hargreaves(self):
        weather = context.build_context()["weather"]
        raw, scaled = wm.precompute_et0(weather, scale=1.0), wm.precompute_et0(weather)
        day = sorted(weather)[100]
        self.assertAlmostEqual(scaled[day], tables.constant("et0_scale") * raw[day])

    def test_the_parameters_lie_inside_the_search_bounds_and_plausible_soils(self):
        params = tables.calibration()["parameters"]
        for (low, high), name in zip(calibration.search_bounds(), wm.PARAMS):
            self.assertTrue(low <= params[name] <= high, name)
        self.assertTrue(tables.constant("available_water_min") <= params["capacity_mm"] <= tables.constant("available_water_max"))

    def test_the_seed_spread_is_reported_and_the_best_calibration_error_was_kept(self):
        doc = tables.calibration()
        errors = {r["seed"]: r["calibration_rmse_m3_m3"] for r in doc["seed_runs"]}
        self.assertEqual(errors[doc["chosen_seed"]], min(errors.values()))
        self.assertEqual(doc["parameters"], next(r["parameters"] for r in doc["seed_runs"] if r["seed"] == doc["chosen_seed"]))

    def test_perfect_agreement_scores_perfectly(self):
        series = {d: 0.2 + 0.001 * i for i, d in enumerate(calibration.days(*calibration.CALIBRATION_PERIOD))}
        scores = calibration.metrics(series, series, calibration.CALIBRATION_PERIOD)
        self.assertEqual((scores["rmse_m3_m3"], scores["correlation"]), (0.0, 1.0))


@unittest.skipUnless(HAVE_SCIPY, "scipy is not installed")
class FitCommand(unittest.TestCase):
    def test_a_short_fit_on_synthetic_nasa_files_returns_a_complete_document(self):
        with tempfile.TemporaryDirectory() as folder:
            _, l4 = fixtures.write_synthetic_smap(folder, context.build_context())
            doc = calibration.calibrate(l4, seeds=(1, 2), maxiter=3, popsize=4)
        self.assertEqual(set(doc["parameters"]), set(wm.PARAMS))
        self.assertEqual(len(doc["seed_runs"]), 2)
        self.assertEqual(doc["et0_scale"], tables.constant("et0_scale"))
        for (low, high), name in zip(calibration.search_bounds(), wm.PARAMS):
            self.assertTrue(low <= doc["parameters"][name] <= high, name)


if __name__ == "__main__":
    unittest.main()
