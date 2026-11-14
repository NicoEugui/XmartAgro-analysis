"""Water scenario tests: structure, honesty flags and consistency. Run: python3 test_scenarios.py"""

import unittest
from xmart_analysis.engine import water_scenarios as ws
import fixtures



class WaterScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {lang: fixtures.water_doc(lang)
                    for lang in ("en", "es")}

    def test_initial_state_is_the_simulated_sensor(self):
        for d in self.docs.values():
            self.assertEqual(d["metadata"]["initial_state_source"], "simulated_iot_sensor")
            self.assertTrue(d["metadata"]["is_simulated_input"])
            self.assertFalse(d["metadata"]["applicable_to_field"])
            self.assertTrue(d["initial_state"]["sensor"]["is_simulated"])
            self.assertIsNone(d["initial_state"]["sensor"]["available_water_mm"])

    def test_the_reading_is_kept_as_received_next_to_what_the_model_used(self):
        for d in self.docs.values():
            state = d["initial_state"]
            self.assertEqual(state["reading_as_received_m3_m3"], 0.28)
            self.assertEqual(state["reading_used_by_model_m3_m3"], 0.28)
            self.assertEqual(state["reading_warnings"], [])

    def test_it_is_not_a_forecast(self):
        for lang, d in self.docs.items():
            self.assertEqual(d["metadata"]["type"], "exploratory_scenario")
            self.assertTrue(d["note"])
            self.assertNotIn("probability", " ".join(d.keys()))

    def test_spread_is_ordered_and_complete(self):
        for d in self.docs.values():
            self.assertEqual(d["scenarios"], len(ws.SEASON_YEARS))
            for row in d["spread_by_day"]:
                self.assertLessEqual(row["p10_mm"], row["median_mm"])
                self.assertLessEqual(row["median_mm"], row["p90_mm"])
            self.assertEqual(d["spread_by_day"][0]["day"], 0)
            self.assertEqual(d["spread_by_day"][-1]["day"], 119)

    def test_three_water_levels_are_kept_apart(self):
        for d in self.docs.values():
            levels = d["initial_state"]["water_levels"]
            self.assertEqual(levels["current_volumetric_moisture"]["status"], "simulated")
            self.assertEqual(levels["current_volumetric_moisture"]["value"], 0.28)
            self.assertIsNone(levels["current_available_water"]["value"])
            self.assertEqual(levels["current_available_water"]["status"], "not_determined")
            self.assertEqual(levels["scenario_initial_water"]["status"], "derived_from_assumptions")
            self.assertTrue(levels["scenario_initial_water"]["value"] > 0)
            self.assertTrue(d["initial_state"]["display_rule"])

    def test_uncertainty_is_declared_as_climate_only(self):
        for d in self.docs.values():
            u = d["uncertainty"]
            self.assertFalse(u["is_confidence_interval"])
            self.assertEqual(u["covers"], ["climate_variability_between_historical_seasons"])
            self.assertEqual(set(u["does_not_cover"]), {"soil_parameters", "sensor_reading", "model_parameters"})
            self.assertTrue(d["spread_label"])

    def test_structural_sensitivity_envelops_the_base_band_in_a_comparable_unit(self):
        for d in self.docs.values():
            ss = d["structural_sensitivity"]
            self.assertEqual(ss["configurations"], 12)
            self.assertFalse(ss["is_confidence_interval"])
            self.assertTrue(ss["comparable_unit_note"] and ss["plausibility_note"])
            base = {r["day"]: r for r in d["spread_by_day"]}
            for e in ss["envelope_by_day_m3_m3"]:
                b = base[e["day"]]
                self.assertLessEqual(e["p10_min_m3_m3"], b["p10_m3_m3"])
                self.assertGreaterEqual(e["p90_max_m3_m3"], b["p90_m3_m3"])
                self.assertLessEqual(e["median_min_m3_m3"], b["median_m3_m3"])
                self.assertGreaterEqual(e["median_max_m3_m3"], b["median_m3_m3"])
            self.assertNotIn("envelope_by_day", ss)  # no envelope in non-comparable millimetres

    def test_implausible_soils_are_excluded_and_reported(self):
        for d in self.docs.values():
            ss = d["structural_sensitivity"]
            self.assertEqual(ss["plausible_configurations"] + len(ss["excluded"]), ss["configurations"])
            for c in ss["excluded"]:
                self.assertTrue(c["violations"])
            for c in ss["configuration_details"]:
                self.assertEqual(c["plausible"], not c["violations"])
                if c["plausible"]:
                    self.assertGreaterEqual(c["wilting_point_m3_m3"], 0.10)
                    self.assertLessEqual(c["field_capacity_m3_m3"], 0.45)

    def test_counts_never_exceed_the_scenarios(self):
        for d in self.docs.values():
            for count in d["scenarios_below_threshold_by_day"].values():
                self.assertLessEqual(count, d["scenarios"])


if __name__ == "__main__":
    unittest.main()
