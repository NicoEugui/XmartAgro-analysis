"""Survey rotations as options: how written crops become modelled crops, and the card at the NASA point."""
import unittest

import fixtures
from xmart_analysis.engine import context, rotations, tables
from xmart_analysis.engine import platform_session as ps
from xmart_analysis.engine import water_model as wm


class Mapping(unittest.TestCase):
    def test_a_soybean_right_after_a_winter_grain_crop_is_second_sowing(self):
        for previous in ("wheat", "barley", "rapeseed"):
            self.assertEqual(rotations.survey_crop_to_engine("soybean", previous), "soybean_2nd", previous)
        for previous in (None, "maize", "oat", "soybean"):
            self.assertEqual(rotations.survey_crop_to_engine("soybean", previous), "soybean_1st", previous)

    def test_crops_without_parameters_are_not_modelled_instead_of_guessed(self):
        for crop in ("vetch", "alfalfa", "sunflower", "cover_crop", "double_crop", "pasture"):
            self.assertIsNone(rotations.survey_crop_to_engine(crop, None), crop)

    def test_the_previous_crop_never_crosses_a_group(self):
        groups = tables.survey_rotations()[9]
        self.assertEqual([e["engine_crop"] for e, g in zip(rotations.entries(9), groups) if g[0] == 4], ["oat_cover", "soybean_1st"])

    def test_maize_stubble_is_not_counted_as_a_maize_crop(self):
        self.assertEqual(sum(c == "maize" for _, c, _ in tables.survey_rotations()[9]), 1)


class Evaluation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kw = {k: v for k, v in context.build_context().items()}

    def test_only_rotations_with_a_modelled_crop_are_offered(self):
        ids = rotations.ids()
        self.assertEqual(len(ids), 10)
        self.assertNotIn("survey_05", ids)  # "several rotations": no crops written
        self.assertNotIn("survey_06", ids)  # "3 double crop and 3 pasture": no crops named

    def test_counts_add_up_and_split_in_ten(self):
        for rotation_id in rotations.ids():
            r = rotations.evaluate(rotation_id, self.kw)
            self.assertEqual(sum(r["season_counts"].values()), r["combinations"], rotation_id)
            self.assertEqual(sum(r["split_in_10_parts"].values()), 10, rotation_id)
            self.assertEqual(r["combinations"], sum(e["scenarios"] for e in r["entries"] if e["status"] == "modelled"), rotation_id)

    def test_the_same_crops_give_the_same_result(self):
        a, b = rotations.evaluate("survey_01", self.kw), rotations.evaluate("survey_02", self.kw)
        self.assertEqual((a["season_counts"], a["crops_modelled"]), (b["season_counts"], b["crops_modelled"]))

    def test_a_cover_crop_reports_no_stress_of_its_own(self):
        statuses = {e["survey_crop"]: e["status"] for e in rotations.entries(11)}
        self.assertEqual((statuses["oat"], statuses["sunflower"]), ("cover_without_risk", "not_modelled"))


class InTheSession(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = context.build_context()

    def session(self, *ids):
        a = fixtures.default_answers()
        a["options"] = [{"kind": "rotation", "rotation": i} for i in ids]
        return ps.build_session(a, context=self.context)

    def test_a_rotation_option_becomes_an_unranked_card(self):
        cards = self.session("survey_03", "survey_10")["outputs"]["option_cards"]
        rotation_cards = [c for c in cards if c["kind"] == "rotation"]
        self.assertEqual([c["id"] for c in rotation_cards], ["survey_03", "survey_10"])
        for c in rotation_cards:
            self.assertEqual(sum(c["split_in_10_parts"].values()), 10)
            self.assertFalse(c["metadata"]["robust_comparison"])
            self.assertNotIn("rank", c)

    def test_an_unknown_rotation_is_rejected_with_the_known_list(self):
        a = fixtures.default_answers()
        a["options"] = [{"kind": "rotation", "rotation": "survey_05"}]
        errors = ps.validate_answers(a)
        self.assertEqual(errors[0]["code"], "unknown_rotation")
        self.assertIn("survey_03", errors[0]["details"]["known"])

    def test_the_session_states_the_nasa_point_it_runs_at(self):
        location = self.session("survey_03")["inputs"]["location"]
        header = wm.POWER_CSV.read_text().split("-END HEADER-")[0]
        self.assertIn(f"{location['latitude']:g}", header)
        self.assertIn(f"{location['longitude']:g}", header)
        self.assertEqual(location["source"], "nasa_power")


if __name__ == "__main__":
    unittest.main()
