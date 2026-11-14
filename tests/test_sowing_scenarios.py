"""Selectable sowing date: stages and windows follow the date, no future climate is used, bad input is rejected.
Run: python3 test_sowing_scenarios.py"""
import unittest
from datetime import date, timedelta

from xmart_analysis.engine import crops_uy as cu
from xmart_analysis.engine import sowing_scenarios as sw
from xmart_analysis.engine import water_model as wm
from xmart_analysis.engine import water_scenarios as ws


class Sowing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cal = wm.load_calibration()
        cls.params = [cal["parameters"][k] for k in wm.PARAMS]
        cls.weather = wm.load_power()
        cls.et0 = wm.precompute_et0(cls.weather)
        cls.kw = {"params": cls.params, "weather": cls.weather, "et0": cls.et0}

    def test_the_date_changes_the_scenarios(self):
        early = sw.evaluate_sowing("soybean_1st", (11, 15), **self.kw)
        late = sw.evaluate_sowing("soybean_1st", (12, 20), **self.kw)
        self.assertNotEqual([r["stress"] for r in early["season_results"]], [r["stress"] for r in late["season_results"]])
        self.assertNotEqual(early["median_water_at_sowing_mm"], late["median_water_at_sowing_mm"])

    def test_stages_and_the_critical_window_follow_the_chosen_date(self):
        a = cu.critical_window_from_sowing("soybean_1st", date(2000, 11, 15))
        b = cu.critical_window_from_sowing("soybean_1st", date(2000, 12, 15))
        self.assertEqual((b[0] - a[0]).days, 30)
        self.assertEqual((b[1] - a[1]).days, 30)
        # the default-date helper agrees with the generalized one
        self.assertEqual(cu.critical_window("soybean_1st", 2000), a)

    def test_sowing_before_the_reading_date_means_next_year(self):
        doc = sw.evaluate_sowing("rapeseed", (5, 1), **self.kw)
        first = doc["season_results"][0]
        self.assertEqual(first["sowing_date"], f"{ws.SEASON_YEARS[0] + 1}-05-01")  # reading on 14 Nov of the first season, sowing the following May
        self.assertGreater(doc["reading"]["median_days_to_sowing"], 150)

    def test_sowing_on_the_reading_date_uses_the_reading_directly(self):
        doc = sw.evaluate_sowing("soybean_1st", (11, 14), **self.kw)
        self.assertEqual(doc["reading"]["median_days_to_sowing"], 0)
        initial = ws.si.to_available_water_mm(0.28, self.params)
        self.assertTrue(all(r["water_at_sowing_mm"] == round(initial, 1) for r in doc["season_results"]))

    def test_no_climate_after_the_end_of_the_cycle_is_used(self):
        doc = sw.evaluate_sowing("soybean_1st", (12, 5), **self.kw)
        target = next(r for r in doc["season_results"] if r["season"] == "1999/00")
        end = date.fromisoformat(target["sowing_date"]) + timedelta(days=cu.cycle_days("soybean_1st") - 1)
        truncated = {d: v for d, v in self.weather.items() if d <= end}
        again = sw.evaluate_sowing("soybean_1st", (12, 5), params=self.params, weather=truncated,
                                   et0={d: v for d, v in self.et0.items() if d <= end})
        same = next(r for r in again["season_results"] if r["season"] == "1999/00")
        self.assertEqual(target, same)

    def test_climate_before_the_reading_date_is_not_used_either(self):
        doc = sw.evaluate_sowing("soybean_1st", (12, 5), **self.kw)
        target = next(r for r in doc["season_results"] if r["season"] == "2005/06")
        start = date(2005, 11, 14)
        trimmed = {d: v for d, v in self.weather.items() if d >= start}
        again = sw.evaluate_sowing("soybean_1st", (12, 5), params=self.params, weather=trimmed,
                                   et0={d: v for d, v in self.et0.items() if d >= start})
        self.assertEqual(target, next(r for r in again["season_results"] if r["season"] == "2005/06"))



    def test_the_fixed_cycle_warning_is_always_present(self):
        for crop, d in (("soybean_1st", (11, 15)), ("wheat", (6, 15)), ("rapeseed", (5, 1))):
            doc = sw.evaluate_sowing(crop, d, **self.kw)
            self.assertIn("cycle_length_fixed", [w["code"] for w in doc["warnings"]])

    def test_the_document_is_labelled_as_not_a_forecast_or_a_yield_prediction(self):
        doc = sw.evaluate_sowing("soybean_1st", (11, 15), **self.kw)
        self.assertFalse(doc["metadata"]["is_forecast"])
        self.assertFalse(doc["metadata"]["is_yield_prediction"])
        self.assertFalse(doc["uncertainty"]["is_confidence_interval"])
        self.assertTrue(doc["no_future_information"] and doc["mm_note"] and doc["question"])

    def test_counts_split_and_bounds(self):
        doc = sw.evaluate_sowing("maize_2nd", (12, 10), **self.kw)
        self.assertEqual(sum(doc["season_counts"].values()), doc["scenarios"])
        self.assertEqual(sum(doc["split_in_10_parts"].values()), 10)
        capacity = self.params[1]
        for row in doc["water_after_sowing"]:
            for key in ("p10_mm", "median_mm", "p90_mm"):
                self.assertTrue(0 <= row[key] <= capacity + 1e-9)
            self.assertLessEqual(row["p10_mm"], row["median_mm"])
            self.assertLessEqual(row["median_mm"], row["p90_mm"])

    def test_rapeseed_is_supported_with_pending_parameters(self):
        spec = cu.CROPS["rapeseed"]
        for parameter in ("sowing", "cycle", "kc", "p"):
            self.assertEqual(spec["status"][parameter], "pending")
        self.assertEqual(cu.cycle_days("rapeseed"), 193)

    def test_a_crop_already_past_its_critical_stage_is_not_given_a_future_sowing(self):
        doc = sw.evaluate_current_crop("wheat", (6, 15), 0.30, (11, 14), **self.kw)  # day 152 of 163, window ended
        self.assertEqual(doc["status"], "critical_stage_passed")
        self.assertEqual(doc["day_of_cycle"], 152)
        self.assertEqual(doc["scenarios"], 0)
        self.assertIsNone(doc["season_counts"])

    def test_a_sowing_date_after_the_reading_is_last_years_and_the_cycle_has_ended(self):
        doc = sw.evaluate_current_crop("soybean_1st", (11, 20), 0.30, (11, 14), **self.kw)
        self.assertEqual(doc["status"], "cycle_ended")
        self.assertGreater(doc["day_of_cycle"], 135)

    def test_a_just_sown_crop_has_its_whole_critical_stage_ahead(self):
        doc = sw.evaluate_current_crop("soybean_1st", (11, 10), 0.30, (11, 14), **self.kw)
        self.assertEqual(doc["status"], "critical_stage_ahead")
        self.assertEqual(doc["day_of_cycle"], 4)
        self.assertEqual(doc["remaining_days"], 131)
        self.assertEqual(doc["critical_stage_remaining_fraction"], 1.0)
        self.assertEqual(sum(doc["season_counts"].values()), doc["scenarios"])

    def test_a_crop_inside_its_critical_stage_evaluates_only_what_remains(self):
        doc = sw.evaluate_current_crop("soybean_1st", (11, 14), 0.30, (1, 20), **self.kw)  # day 67 of 135, window 50-109
        self.assertEqual(doc["status"], "in_critical_stage")
        self.assertLess(doc["critical_stage_remaining_fraction"], 1.0)
        self.assertGreater(doc["critical_stage_remaining_fraction"], 0.0)

    def test_the_current_crop_uses_today_not_a_new_sowing(self):
        # same crop, same date: the future-sowing engine and the current-crop engine must answer differently
        future = sw.evaluate_sowing("soybean_1st", (11, 10), 0.30, (11, 14), **self.kw)
        current = sw.evaluate_current_crop("soybean_1st", (11, 10), 0.30, (11, 14), **self.kw)
        self.assertNotEqual(future["season_counts"], current["season_counts"])
        self.assertEqual(current["day_of_cycle"], 4)

    def test_the_current_crop_evaluation_uses_no_future_climate(self):
        from datetime import date as d, timedelta as td
        doc = sw.evaluate_current_crop("soybean_1st", (11, 10), 0.30, (11, 14), **self.kw)
        target = next(r for r in doc["season_results"] if r["season"] == "2003/04")
        end = d(2003, 11, 14) + td(days=doc["remaining_days"] - 1)
        weather = {k: v for k, v in self.weather.items() if k <= end}
        again = sw.evaluate_current_crop("soybean_1st", (11, 10), 0.30, (11, 14), params=self.params, weather=weather,
                                         et0={k: v for k, v in self.et0.items() if k <= end})
        self.assertEqual(target, next(r for r in again["season_results"] if r["season"] == "2003/04"))

    def test_compare_sowing_dates_is_never_a_robust_ranking(self):
        out = sw.compare_sowing_dates("soybean_1st", [(11, 15), (12, 5), (12, 20)], **self.kw)
        self.assertFalse(out["robust_comparison"])
        self.assertEqual(len(out["dates"]), 3)


if __name__ == "__main__":
    unittest.main()
