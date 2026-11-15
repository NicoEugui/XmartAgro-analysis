"""The backtest: what the tool would have said before each past season, without knowing that season, against what the season was."""

import unittest
from datetime import timedelta

from xmart_analysis.engine import tables
from xmart_analysis.learning import examples, fields, producers, retrospective


class Case(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = examples.Panel()
        cls.field = fields.get("soriano")
        cls.context = cls.panel.contexts["soriano"]

    def test_the_season_itself_is_left_out_and_the_drops_are_ten(self):
        row = retrospective.case(self.field, self.context, "soybean_1st", 2022)
        self.assertEqual(row["seasons_applied"], len(tables.season_years()) - 1)
        self.assertEqual(sum(row["drops"].values()), 10)
        self.assertEqual(set(row["drops"]), {"ok", "tight", "out"})

    def test_what_the_season_brings_does_not_change_what_the_tool_said(self):
        row = retrospective.case(self.field, self.context, "soybean_1st", 2022)
        sowing = producers.sowing_date("soybean_1st", 2022)
        dry = {**self.context["weather"]}
        for i in range(0, 160):  # the season's own rain, from sowing on, is taken away
            day = sowing + timedelta(days=i)
            dry[day] = {**dry[day], "PRECTOTCORR": 0.0}
        changed = retrospective.case(self.field, {**self.context, "weather": dry}, "soybean_1st", 2022)
        self.assertEqual((changed["drops"], changed["risk"]), (row["drops"], row["risk"]))  # the tool did not know
        self.assertGreater(changed["actual_stress"], row["actual_stress"])  # the season did

    def test_a_case_is_the_same_every_time_and_its_flags_follow_its_numbers(self):
        a = retrospective.case(self.field, self.context, "maize", 2015)
        self.assertEqual(a, retrospective.case(self.field, self.context, "maize", 2015))
        self.assertEqual(a["warned"], a["risk"] in ("medium", "high"))
        self.assertEqual(a["ended_out"], a["actual_class"] == "out")

    def test_a_season_the_climate_record_does_not_cover_is_not_a_case(self):
        self.assertIsNone(retrospective.case(self.field, self.context, "maize", 1985))
        self.assertIsNone(retrospective.case(self.field, self.context, "soybean_1st", 2026))


class Document(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = retrospective.run()

    def test_it_says_it_is_simulated_and_covers_four_crops_in_eight_fields_over_every_season(self):
        self.assertTrue(self.doc["simulated"])
        self.assertEqual(self.doc["crops"], list(retrospective.CROPS))
        self.assertLessEqual(self.doc["summary"]["cases"], 4 * 8 * len(tables.season_years()))
        self.assertGreater(self.doc["summary"]["cases"], 1200)

    def test_the_drought_of_2022_23_ended_without_water_in_every_field_and_was_worse_than_almost_every_other_season(self):
        feat = self.doc["featured"]
        self.assertEqual((feat["crop"], feat["season"]), ("soybean_1st", "2022/23"))
        self.assertEqual(len(feat["rows"]), 8)
        for row in feat["rows"]:
            self.assertTrue(row["ended_out"], row["field_id"])
            self.assertGreater(row["actual_stress"], 0.7, row["field_id"])
            self.assertGreaterEqual(row["worse_than_share"], 0.9, row["field_id"])
            self.assertIn(row["risk"], ("medium", "high"))

    def test_a_high_warning_adds_little_for_summer_crops_because_most_summers_end_without_water(self):
        soy = self.doc["by_crop"]["soybean_1st"]
        self.assertGreater(soy["base_rate_out"], 0.5)  # crop parameters are pending: soybean 'fails' in most years
        self.assertLess(abs(soy["out_of_high_risk"] - soy["base_rate_out"]), 0.1)

    def test_winter_crops_rarely_end_without_water(self):
        for crop in ("wheat", "barley"):
            self.assertLess(self.doc["by_crop"][crop]["base_rate_out"], 0.15, crop)

    def test_the_summary_adds_up(self):
        for key in ("summary", "producers_summary"):
            s = self.doc[key]
            self.assertLessEqual(s["ended_out"], s["cases"])
            self.assertLessEqual(s["high_risk_cases"], s["cases"])
        mine = self.doc["producers"]
        self.assertEqual(retrospective.summary(mine), self.doc["producers_summary"])
        self.assertEqual({r["rating"] for r in mine}, {1, 2, 3, 4, 5})
        self.assertTrue(all(r["producer_id"] and r["crop"] != producers.FALLOW for r in mine))

    def test_the_seasons_the_producers_named_are_the_ones_with_the_highest_mean_stress(self):
        check = self.doc["survey_check"]
        named = {r["season"] for r in sorted(check, key=lambda r: -r["producers_naming_it"])[:2]}
        for crop in retrospective.SURVEY_CROPS:
            highest = {r["season"] for r in sorted(check, key=lambda r: -r[f"{crop}_mean_stress"])[:2]}
            self.assertEqual(highest, named, crop)
        self.assertEqual(named, {"2022/23", "2025/26"})  # what the survey says, real data

    def test_a_caller_cannot_change_what_the_next_one_gets(self):
        mine = retrospective.run()
        mine["summary"]["cases"] = -1
        self.assertGreater(retrospective.run()["summary"]["cases"], 0)


if __name__ == "__main__":
    unittest.main()
