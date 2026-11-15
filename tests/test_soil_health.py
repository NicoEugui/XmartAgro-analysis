"""Soil health: what a rotation does to the soil, by rules, and what the producers' own rotations do to their fields."""

import importlib.util
import unittest

from xmart_analysis.engine import soil_health as sh
from xmart_analysis.engine import tables

HAVE_LEARN = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "sklearn"))
GOOD_PLAN = {"organic_matter_pct": 4.5, "erosion_t_ha_yr": 2.0}
BAD_PLAN = {"organic_matter_pct": 1.8, "erosion_t_ha_yr": 12.0}


class Rules(unittest.TestCase):
    def test_every_crop_the_model_or_the_survey_names_has_a_soil_effect(self):
        effects = tables.soil_effects()
        for crop in (*tables.crops(), *tables.unsupported_crops(), "fallow", "pasture", "vetch", "cover_crop", "alfalfa", "double_crop"):
            if crop not in ("carinata",):  # carinata is not grown by anyone surveyed
                self.assertIn(crop, effects, crop)

    def test_bare_months_follow_the_cycle_and_cover_keeps_the_soil_covered(self):
        self.assertAlmostEqual(sh.bare_months("maize"), 12 - 150 / 30.4, places=2)
        self.assertEqual(sh.bare_months("pasture"), 0.0)
        self.assertEqual(sh.bare_months("oat_cover"), 0.0)
        self.assertEqual(sh.bare_months("fallow"), 12.0)
        self.assertGreater(sh.bare_months("sunflower"), 0)  # no calendar in the table: the default cycle

    def test_stubble_and_cover_make_a_better_soil_than_soybeans_and_bare_ground(self):
        stubble = sh.assess(["maize", "wheat", "pasture", "maize", "oat_cover"])
        soy = sh.assess(["soybean_1st"] * 5)
        bare = sh.assess(["fallow"] * 5)
        self.assertEqual(stubble["state"], "good")
        self.assertEqual({soy["state"], bare["state"]}, {"poor"})
        self.assertGreater(stubble["score"], soy["score"])

    def test_soybean_after_soybean_costs_score_up_to_a_cap(self):
        self.assertEqual(sh.soybean_streak(["maize", "soybean_1st", "soybean_2nd", "soybean_2nd"]), 3)
        self.assertEqual(sh.soybean_streak(["soybean_1st", "maize"]), 0)
        one, three, many = (sh.assess(["maize", "maize"] + ["soybean_1st"] * n)["soybean_streak_penalty"] for n in (1, 3, 9))
        self.assertEqual(one, 0)
        self.assertEqual(three, 1.0)
        self.assertEqual(many, tables.constant("soil_soy_streak_cap"))

    def test_the_analysis_moves_the_score_and_without_it_the_precision_is_low(self):
        crops = ["wheat", "soybean_2nd", "maize", "barley", "soybean_2nd"]
        plain, good, bad = sh.assess(crops), sh.assess(crops, GOOD_PLAN), sh.assess(crops, BAD_PLAN)
        self.assertEqual((plain["precision"], good["precision"]), ("low", "medium"))
        self.assertGreater(good["score"], plain["score"])
        self.assertLess(bad["score"], plain["score"])
        self.assertEqual(bad["analysis_reasons"], ["erosion_above_tolerance", "low_organic_matter"])
        self.assertEqual(good["analysis_reasons"], ["high_organic_matter"])

    def test_the_trend_compares_the_two_halves_and_needs_enough_seasons(self):
        self.assertEqual(sh.assess(["fallow", "fallow", "maize", "pasture"])["trend"], "improving")
        self.assertEqual(sh.assess(["pasture", "maize", "fallow", "soybean_1st"])["trend"], "worsening")
        self.assertEqual(sh.assess(["maize", "wheat", "maize", "wheat"])["trend"], "stable")
        self.assertEqual(sh.assess(["maize", "wheat", "fallow"])["trend"], "unknown")

    def test_the_effect_of_a_rotation_needs_no_analysis(self):
        self.assertEqual(sh.effect(["maize", "pasture", "wheat", "pasture"])["effect"], "improves")
        self.assertEqual(sh.effect(["soybean_1st", "soybean_1st", "soybean_1st"])["effect"], "worsens")
        self.assertEqual(sh.effect(["wheat", "soybean_2nd", "maize", "barley"])["effect"], "maintains")


@unittest.skipUnless(HAVE_LEARN, "numpy, scipy and scikit-learn are not installed")
class Producers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from xmart_analysis.learning import soil_health
        cls.rows = soil_health.producer_table()

    def test_one_row_per_producer_with_five_seasons_of_the_rotation_they_wrote(self):
        self.assertEqual([r["producer_id"] for r in self.rows], [f"p{i:02d}" for i in range(1, 13)])
        for r in self.rows:
            self.assertEqual(len(r["crops"]), 5)
            self.assertEqual((len(r["season_names"]), r["seasons"]), (5, 5))
            self.assertTrue(set(r["crops"]) <= set(tables.soil_effects()))

    def test_every_row_says_that_the_rotation_years_and_the_analysis_are_simulated(self):
        for r in self.rows:
            self.assertTrue(r["simulated"])
            self.assertEqual(r["soil_analysis_status"], "simulated")
            self.assertEqual(r["precision"], "medium")
            self.assertIn(r["state"], ("good", "regular", "poor"))
            self.assertIn(r["trend"], ("improving", "stable", "worsening", "unknown"))
            self.assertIn(r["rotation_effect"], ("improves", "maintains", "worsens"))

    def test_the_producer_who_wrote_pastures_has_a_better_soil_than_the_one_on_a_steep_field_with_little_organic_matter(self):
        by_id = {r["producer_id"]: r for r in self.rows}
        self.assertGreater(by_id["p06"]["score"], by_id["p08"]["score"])


if __name__ == "__main__":
    unittest.main()
