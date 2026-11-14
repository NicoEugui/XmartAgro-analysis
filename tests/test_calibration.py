"""Calibration: the shipped parameters match the corrected demand, stay in plausible soils and the fit command runs."""
import importlib.util
import tempfile
import unittest

import fixtures
from xmart_analysis import calibration
from xmart_analysis.engine import context, tables
from xmart_analysis.engine import water_model as wm

HAVE_SCIPY = importlib.util.find_spec("scipy") is not None


class ShippedCalibration(unittest.TestCase):
    def test_it_records_the_point_it_was_fitted_at_and_that_is_the_site(self):
        fit = tables.calibration()
        self.assertEqual(set(fit["point"]), {"latitude", "longitude"})
        self.assertTrue(tables.calibration_is_current())
        self.assertNotIn("et0_scale", fit)

    def test_the_parameters_lie_inside_the_search_bounds_and_plausible_soils(self):
        params = tables.calibration()["parameters"]
        for (low, high), name in zip(calibration.search_bounds(), wm.PARAMS):
            self.assertTrue(low <= params[name] <= high, name)
        self.assertTrue(tables.constant("available_water_min") <= params["capacity_mm"] <= tables.constant("available_water_max"))

    def test_the_seed_spread_is_reported_and_the_chosen_run_fits_as_well_as_the_best(self):
        doc = tables.calibration()
        errors = {r["seed"]: r["calibration_rmse_m3_m3"] for r in doc["seed_runs"]}
        self.assertLessEqual(errors[doc["chosen_seed"]], min(errors.values()) * (1 + calibration.TOLERANCE))
        self.assertEqual(doc["parameters"], next(r["parameters"] for r in doc["seed_runs"] if r["seed"] == doc["chosen_seed"]))

    def test_one_odd_optimum_is_not_chosen_for_a_tiny_gain(self):
        bounds = calibration.search_bounds()
        usual = {"theta_min": 0.19, "capacity_mm": 162.0, "kc": 0.93, "stress_threshold": 0.69, "drainage_onset_fraction": 0.95,
                 "daily_drainage": 0.28}
        odd = {**usual, "kc": 0.63, "stress_threshold": 0.57, "drainage_onset_fraction": 0.42, "daily_drainage": 0.008}
        runs = [{"seed": 1, "calibration_rmse_m3_m3": 0.02356, "parameters": usual}, {"seed": 2, "calibration_rmse_m3_m3": 0.02357, "parameters": dict(usual)},
                {"seed": 3, "calibration_rmse_m3_m3": 0.02349, "parameters": odd}, {"seed": 4, "calibration_rmse_m3_m3": 0.02358, "parameters": dict(usual)}]
        self.assertEqual(calibration.choose(runs, bounds)["seed"], 1)
        far = [dict(runs[2], calibration_rmse_m3_m3=0.01), *runs[:2]]
        self.assertEqual(calibration.choose(far, bounds)["seed"], 3)  # clearly better: no tie, so it wins

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
        for (low, high), name in zip(calibration.search_bounds(), wm.PARAMS):
            self.assertTrue(low <= doc["parameters"][name] <= high, name)


if __name__ == "__main__":
    unittest.main()
