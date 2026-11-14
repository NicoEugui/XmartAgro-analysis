"""Session tests: the data requested is what the output needs and answers are validated."""
import json
import unittest
from datetime import datetime, timedelta, timezone

import fixtures
from xmart_analysis.engine import platform_contract as pc
from xmart_analysis.engine import platform_session as ps
from xmart_analysis.engine import context
from xmart_analysis.engine import sensor_sources as ss
from xmart_analysis.engine.errors import EngineError

def answers():
    return fixtures.default_answers()


def perturb(field):
    """A changed copy of the default answers where only `field` differs."""
    a = answers()
    if field == "sensor.moisture":
        a["sensor"] = {"source": "manual", "moisture": 0.33}
    elif field == "reading_date":
        a["reading_date"] = "03-15"
    elif field == "current_crop.crop":
        a["current_crop"]["crop"] = "wheat"
    elif field == "current_crop.sowing":
        a["current_crop"]["sowing"] = "12-20"
    elif field == "options":
        a["options"] = a["options"][:2]
    elif field == "past_seasons.crops":
        a["past_seasons"][0]["crops"] = ["sunflower"]
    elif field == "past_seasons.rating":
        a["past_seasons"][0]["rating"] = 5
    elif field == "past_seasons.yield_kg_ha":
        a["past_seasons"][0]["yield_kg_ha"] = 3100
    elif field == "agronomist.analysis_date":
        a["agronomist"]["analysis_date"] = "2025-01"
    elif field == "agronomist.organic_matter_pct":
        a["agronomist"]["organic_matter_pct"] = 6.0
    elif field == "agronomist.phosphorus_ppm":
        a["agronomist"]["phosphorus_ppm"] = 40
    elif field == "agronomist.ph":
        a["agronomist"]["ph"] = 7.2
    elif field == "agronomist.erosion_t_ha_yr":
        a["agronomist"]["erosion_t_ha_yr"] = 20.0
    elif field == "agronomist.soil_type":
        a["agronomist"]["soil_type"] = "CONEAT 9.1, Vertisol"
        a["agronomist"]["soil_type_confirmed"] = False
    else:
        raise AssertionError(f"No perturbation defined for contract field {field}")
    return a


class Fixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from xmart_analysis.engine import context
        cls.context = context.build_context()
        cls.base = ps.build_session(answers(), context=cls.context)
        cls.base_fp = ps.engine_fingerprint(cls.base)


class InputOutputDependence(Fixtures):
    """How we know the platform asks for the right data: fields marked `used` change the engine output and fields
    marked `stored_only` do not."""

    def test_every_contract_field_has_a_perturbation_so_new_fields_cannot_slip_in(self):
        for f in pc.INPUT_FIELDS:
            perturb(f["field"])

    def test_changing_a_used_field_changes_the_engine_output(self):
        for field in pc.used_fields():
            session = ps.build_session(perturb(field), context=self.context)
            self.assertNotEqual(ps.engine_fingerprint(session), self.base_fp, f"{field} is declared used but changes nothing")

    def test_changing_a_stored_field_does_not_change_the_engine_output(self):
        for field in pc.stored_fields():
            session = ps.build_session(perturb(field), context=self.context)
            self.assertEqual(ps.engine_fingerprint(session), self.base_fp, f"{field} is declared stored but changes the output")

    def test_a_stored_field_still_shows_up_in_the_data_sheet(self):
        for field in pc.stored_fields():
            session = ps.build_session(perturb(field), context=self.context)
            before = {r["field"]: r["value"] for r in self.base["data_sheet"]["rows"]}
            after = {r["field"]: r["value"] for r in session["data_sheet"]["rows"]}
            self.assertNotEqual(before[field], after[field], field)

    def test_each_output_lists_only_fields_that_exist_in_the_contract(self):
        names = {f["field"] for f in pc.INPUT_FIELDS}
        for output in pc.OUTPUTS:
            self.assertTrue(set(pc.fields_for_output(output)) <= names)
        self.assertTrue(set(pc.used_fields()).isdisjoint(pc.stored_fields()))

    def test_the_data_sheet_rows_match_the_contract_and_its_status(self):
        rows = {r["field"]: r for r in self.base["data_sheet"]["rows"]}
        self.assertEqual(set(rows), {f["field"] for f in pc.INPUT_FIELDS})
        for f in pc.INPUT_FIELDS:
            self.assertEqual(rows[f["field"]]["status"], f["status"])


class ClosedLists(Fixtures):
    """Choices are dropdowns, never free text."""

    def test_free_text_crops_in_history_are_rejected_with_the_allowed_list(self):
        for bad in ("Cebada + soja de segunda", ["Soja de primera"], ["soja"], ["banana"]):
            a = answers()
            a["past_seasons"][0]["crops"] = bad
            errors = ps.validate_answers(a)
            self.assertTrue(errors, bad)
            self.assertEqual(errors[0]["code"], "invalid_choice")
            self.assertEqual(errors[0]["field"], "past_seasons[0].crops")

    def test_history_accepts_only_offered_crops_including_unsimulated_ones(self):
        a = answers()
        a["past_seasons"][0]["crops"] = ["sunflower", "fallow", "pasture_mix"]
        self.assertEqual(ps.validate_answers(a), [])

    def test_a_season_must_be_one_of_the_offered_seasons_and_only_once(self):
        a = answers()
        a["past_seasons"][0]["season"] = "2019 2020"
        self.assertEqual(ps.validate_answers(a)[0]["code"], "invalid_choice")
        b = answers()
        b["past_seasons"][1]["season"] = b["past_seasons"][0]["season"]
        self.assertIn("duplicate_season", [e["code"] for e in ps.validate_answers(b)])

    def test_the_current_crop_and_options_reject_names_typed_as_text(self):
        for crop in ("Soja de segunda", "soja", "wheat "):
            a = answers()
            a["current_crop"]["crop"] = crop
            self.assertTrue(ps.validate_answers(a), crop)

    def test_the_data_sheet_shows_crop_names_from_the_ids(self):
        row = next(r for r in self.base["data_sheet"]["rows"] if r["field"] == "past_seasons.crops")
        self.assertEqual(row["value"][0], ["barley", "soybean_2nd"])






class WarningsAreTranslatedAndHonest(Fixtures):

    def test_a_sowing_many_months_after_the_reading_is_flagged_as_nearly_climatological(self):
        from xmart_analysis.engine import sowing_scenarios as sw
        self.assertEqual(sw.days_until_sowing((10, 15), (11, 14)), 335)
        self.assertEqual(sw.days_until_sowing((11, 15), (11, 14)), 1)
        far = sw.far_sowing_warning((10, 15), (11, 14))
        self.assertEqual(far["code"], "sowing_far_from_reading")
        self.assertIn("335", far["label"]["es"])
        self.assertIsNone(sw.far_sowing_warning((11, 15), (11, 14)))
        self.assertIsNone(sw.far_sowing_warning((3, 10), (11, 14)) if sw.days_until_sowing((3, 10), (11, 14)) <= 120 else None)

    def test_the_card_of_a_far_option_carries_the_warning_and_a_near_one_does_not(self):
        a = answers()
        a["options"] = [{"kind": "crop", "crop": "maize", "sowing": "10-15"}, {"kind": "crop", "crop": "soybean_1st", "sowing": "11-15"}]
        cards = ps.build_session(a, context=self.context)["outputs"]["option_cards"]
        codes = {c["id"]: [w["code"] for w in c["warnings"]] for c in cards}
        self.assertIn("sowing_far_from_reading", codes["maize@10-15"])
        self.assertNotIn("sowing_far_from_reading", codes["soybean_1st@11-15"])

    def test_the_current_crop_is_never_flagged_as_far_because_it_is_already_sown(self):
        a = answers()
        a["current_crop"] = {"crop": "wheat", "sowing": "06-15"}
        card = ps.build_session(a, context=self.context)["outputs"]["option_cards"][0]
        self.assertNotIn("sowing_far_from_reading", [w["code"] for w in card["warnings"]])


class ManualReadingIsNotCalledSimulated(Fixtures):
    def _session(self, source):
        a = answers()
        a["sensor"] = {"source": "manual", "moisture": 0.24} if source == "manual" else {"source": "simulated"}
        return ps.build_session(a, context=self.context)

    def test_a_typed_value_is_never_described_as_a_simulated_sensor(self):
        from xmart_analysis.engine.i18n import resolve
        text = json.dumps(resolve(self._session("manual"), "es"), ensure_ascii=False).lower()
        self.assertNotIn("sensor simulad", text.replace("(simulada o escrita)", ""))
        self.assertNotIn("(simulada)", text)
        self.assertIn("escrito por una persona", text)

    def test_the_simulated_sensor_still_says_so(self):
        from xmart_analysis.engine.i18n import resolve
        self.assertIn("simulada", json.dumps(resolve(self._session("simulated"), "es"), ensure_ascii=False).lower())

    def test_the_reading_day_is_shown_even_without_a_timestamp(self):
        sw = self._session("manual")["outputs"]["main_screen"]["soil_water"]
        self.assertEqual(sw["reading_day"], "11-14")
        self.assertIsNone(sw["reading_date"])




class CurrentCropCard(Fixtures):
    def session_with(self, crop, sowing):
        a = answers()
        a["current_crop"] = {"crop": crop, "sowing": sowing}
        a["options"] = [{"kind": "crop", "crop": "maize_2nd", "sowing": "12-10"}]
        return ps.build_session(a, context=self.context)

    def test_a_crop_past_its_critical_stage_gets_no_deficit_drops(self):
        # a real session: wheat sown on 15 June, reading on 14 November
        card = self.session_with("wheat", "06-15")["outputs"]["option_cards"][0]
        self.assertTrue(card["is_current"])
        self.assertEqual(card["status"], "critical_stage_passed")
        self.assertIsNone(card["split_in_10_parts"])
        self.assertIsNone(card["high_deficit_seasons"])
        self.assertEqual(card["scenarios"], 0)

    def test_an_ended_cycle_is_reported_as_such(self):
        card = self.session_with("soybean_1st", "11-20")["outputs"]["option_cards"][0]
        self.assertEqual(card["status"], "cycle_ended")
        self.assertIsNone(card["split_in_10_parts"])

    def test_a_just_sown_crop_has_drops_and_a_stage_status(self):
        card = self.session_with("soybean_1st", "11-10")["outputs"]["option_cards"][0]
        self.assertEqual(card["status"], "critical_stage_ahead")
        self.assertEqual(sum(card["split_in_10_parts"].values()), 10)
        self.assertEqual(card["day_of_cycle"], 4)


class Validation(Fixtures):
    def test_all_problems_are_reported_together_with_their_field(self):
        bad = {"sensor": {"source": "manual", "moisture": 0.9}, "reading_date": "13-45",
               "current_crop": {"crop": "lotus", "sowing": "11-15"},
               "past_seasons": [{"season": "2025", "rating": 7, "yield_kg_ha": 99999}],
               "agronomist": {"organic_matter_pct": 99, "ph": 12, "analysis_date": "May 2026"}, "options": []}
        errors = ps.validate_answers(bad)
        fields = {e["field"] for e in errors}
        self.assertTrue({"sensor.moisture", "reading_date", "current_crop.crop", "past_seasons[0].season",
                         "past_seasons[0].rating", "past_seasons[0].yield_kg_ha", "agronomist.organic_matter_pct",
                         "agronomist.ph", "agronomist.analysis_date", "options"} <= fields, fields)
        for e in errors:
            self.assertTrue(e["code"] and e["message"])

    def test_build_session_refuses_invalid_answers_with_the_error_list(self):
        bad = answers()
        bad["options"] = []
        with self.assertRaises(EngineError) as ctx:
            ps.build_session(bad, context=self.context)
        self.assertEqual(ctx.exception.code, "invalid_answers")
        self.assertEqual(ctx.exception.details["errors"][0]["field"], "options")

    def test_valid_demo_answers_have_no_errors(self):
        self.assertEqual(ps.validate_answers(answers()), [])

    def test_unsupported_and_unsowable_crops_are_rejected_in_options(self):
        for crop in ("sunflower", "lotus", "oat_cover", "nonsense"):
            a = answers()
            a["options"] = [{"kind": "crop", "crop": crop, "sowing": "11-15"}]
            self.assertTrue(ps.validate_answers(a), crop)

    def test_too_many_options_and_duplicates(self):
        a = answers()
        a["options"] = [{"kind": "crop", "crop": "wheat", "sowing": "06-15"}] * (ps.MAX_OPTIONS + 1)
        self.assertEqual(ps.validate_answers(a)[0]["code"], "too_many_options")
        a["options"] = [{"kind": "crop", "crop": "soybean_1st", "sowing": "11-10"}, {"kind": "crop", "crop": "maize_2nd", "sowing": "12-10"}]
        session = ps.build_session(a, context=self.context)
        self.assertEqual(len(session["outputs"]["option_cards"]), 2)  # the option equal to the current sowing is not repeated

    def test_the_current_crop_always_comes_first_and_is_marked(self):
        cards = self.base["outputs"]["option_cards"]
        self.assertTrue(cards[0]["is_current"])
        self.assertFalse(any(c["is_current"] for c in cards[1:]))

    def test_cards_never_rank_the_options(self):
        for card in self.base["outputs"]["option_cards"]:
            self.assertNotIn("rank", card)
            self.assertNotIn("best", card)
            self.assertEqual(card["confidence"], "low")
            self.assertEqual(card["soil"]["state"], "no_field_diagnosis")
            self.assertEqual(sum(card["split_in_10_parts"].values()), 10)

    def test_the_main_screen_never_shows_a_millimetre_figure_as_the_current_water(self):
        sw = self.base["outputs"]["main_screen"]["soil_water"]
        self.assertIsNone(sw["available_water_mm"])
        self.assertEqual(sw["available_water_status"], "not_determined")


class StoredReadingContract(unittest.TestCase):
    NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)

    def parse(self, **override):
        payload = {"sensor_id": "ok", "timestamp": (self.NOW - timedelta(hours=1)).isoformat(), "volumetric_moisture": 0.31,
                   "unit": "m3/m3", "depth_cm": 30, **override}
        return ss.parse_reading({k: v for k, v in payload.items() if v is not None}, self.NOW)

    def test_a_good_reading_is_real_but_unvalidated(self):
        info = self.parse()
        self.assertEqual((info["source"], info["is_simulated"], info["depth_cm"], info["warnings"]),
                         ("backend_api_sensor", False, 30, []))

    def test_stale_future_and_missing_depth_are_flagged_not_hidden(self):
        self.assertEqual(self.parse(timestamp=(self.NOW - timedelta(hours=40)).isoformat())["warnings"], ["stale_reading"])
        self.assertEqual(self.parse(timestamp=(self.NOW + timedelta(hours=3)).isoformat())["warnings"], ["future_timestamp"])
        info = self.parse(depth_cm=None)
        self.assertEqual((info["warnings"], info["depth_cm"]), (["depth_unknown"], None))

    def test_bad_payloads_are_structured_errors(self):
        def code(**kw):
            with self.assertRaises(EngineError) as ctx:
                self.parse(**kw)
            return ctx.exception.code
        self.assertEqual(code(unit="%"), "sensor_unit_unsupported")
        self.assertEqual(code(volumetric_moisture=0.95), "moisture_out_of_range")
        self.assertEqual(code(timestamp="yesterday"), "sensor_payload_invalid")
        with self.assertRaises(EngineError) as ctx:
            ss.parse_reading({"unit": "m3/m3"}, self.NOW)
        self.assertEqual(ctx.exception.code, "sensor_payload_invalid")

    def test_a_session_fed_by_a_stored_reading_uses_its_reading_and_its_own_date(self):
        session = ps.build_session(answers(), sensor_info=self.parse(), context=context.build_context())
        main = session["outputs"]["main_screen"]
        self.assertEqual(main["soil_water"]["source"], "backend_api_sensor")
        self.assertFalse(main["scenarios"]["metadata"]["is_simulated_input"])
        self.assertEqual(session["inputs"]["reading_date"], "11-14")
        self.assertEqual(main["soil_water"]["reading_validation"]["depth_cm"], 30)
        self.assertEqual(main["soil_water"]["reading_validation"]["calibration"], "pending")


if __name__ == "__main__":
    unittest.main()
