"""The static JSON for the frontend: the API contract's shape, filled with the model's results, documented field by field."""
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import schema_check
from xmart_analysis import cli
from xmart_analysis.engine import platform_session as ps
from xmart_analysis.engine import water_scenarios as ws
from xmart_analysis.frontend import payload, schema

REPO = Path(__file__).resolve().parents[1]
NOW = "2026-11-14T10:30:00+00:00"
HAVE_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
# What the panel's API contract names (backend docs/API.md): the frontend maps these fields without extra logic.
API_SUMMARY = {"field", "mock", "generated_at", "water", "soil", "options"}
API_WATER = {"mm", "capacity_mm", "source", "reliability", "updated_at"}
API_SOIL = {"state", "trend", "precision", "reasons", "missing"}
API_OPTION = {"id", "name", "is_current", "water_risk", "drops", "sentence", "soil_effect", "soil_reason", "why", "evidence", "benefits",
              "gaps", "risks"}
API_SCENARIOS = {"from_year", "to_year", "options"}


def export(folder, *extra):
    assert cli.main(["export", "--out", str(folder), "--now", NOW, *extra]) == 0
    return json.loads((Path(folder) / "frontend.json").read_text(encoding="utf-8"))


def walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


class Export(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.doc = export(cls.dir.name)
        cls.schema = schema.build()
        cls.summary = cls.doc["summary"]

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_the_document_follows_the_schema(self):
        self.assertEqual(schema_check.problems(self.doc, self.schema, self.schema), [])

    @unittest.skipUnless(HAVE_JSONSCHEMA, "jsonschema is not installed")
    def test_a_standard_validator_agrees(self):
        import jsonschema
        jsonschema.Draft202012Validator.check_schema(self.schema)
        jsonschema.validate(self.doc, self.schema, cls=jsonschema.Draft202012Validator, format_checker=jsonschema.FormatChecker())

    def test_every_field_says_what_it_means_and_where_it_is_used(self):
        self.assertEqual(schema_check.missing(self.schema, "description"), [])
        self.assertEqual(schema_check.missing(self.schema, "x-used-in"), [])

    def test_the_checker_rejects_what_it_should(self):
        broken = json.loads(json.dumps(self.doc))
        del broken["site"]["soil_calibration"]
        broken["site"]["extra"] = 1
        broken["summary"]["water"]["mm"] = "much"
        broken["summary"]["options"][0]["water_risk"] = "huge"
        found = " ".join(schema_check.problems(broken, self.schema, self.schema))
        for expected in ("missing soil_calibration", "unexpected field extra", "expected number", "matches none"):
            self.assertIn(expected, found)

    def test_summary_inputs_and_scenarios_have_the_names_of_the_api_contract(self):
        self.assertEqual(set(self.summary), API_SUMMARY)
        self.assertTrue(API_WATER <= set(self.summary["water"]))
        self.assertEqual(set(self.summary["soil"]), API_SOIL)
        for option in self.summary["options"]:
            self.assertTrue(API_OPTION <= set(option), option["id"])
        self.assertEqual(set(self.doc["scenarios"]), API_SCENARIOS)
        self.assertEqual(set(self.doc["inputs"]), {"farmer", "agronomist"})

    def test_every_text_is_in_both_languages(self):
        texts = [d for d in walk(self.doc) if set(d) == {"key", "en", "es"}]
        self.assertGreater(len(texts), 40)
        for t in texts:
            self.assertTrue(t["en"].strip() and t["es"].strip(), t["key"])

    def test_nothing_is_ranked_scored_or_forecast(self):
        forbidden = {"rank", "ranking", "score", "best", "probability", "forecast"}
        self.assertEqual({k for d in walk(self.doc) for k in d} & forbidden, set())
        self.assertTrue(self.doc["status"]["exploratory"])
        self.assertFalse(self.doc["status"]["validated_for_field"])
        self.assertTrue(self.doc["status"]["simulated_reading"])

    def test_what_the_model_does_not_know_is_null_and_not_invented(self):
        soil = self.summary["soil"]
        self.assertEqual((soil["state"], soil["trend"], soil["reasons"]), (None, None, []))
        self.assertEqual(soil["precision"], "low")
        self.assertTrue(soil["missing"])
        for option in self.summary["options"]:
            self.assertEqual((option["soil_effect"], option["soil_reason"], option["why"]), (None, None, None))
            self.assertEqual((option["evidence"], option["benefits"], option["risks"]), ([], [], []))

    def test_the_water_header_is_an_estimate_labelled_as_such(self):
        water = self.summary["water"]
        self.assertEqual((water["source"], water["reliability"], water["mm_status"]), ("sensor", "low", "derived_from_assumptions"))
        self.assertTrue(water["is_simulated"])
        self.assertTrue(0 < water["mm"] < water["capacity_mm"])

    def test_the_current_crop_comes_first_and_the_cards_are_complete(self):
        options = self.summary["options"]
        self.assertTrue(options[0]["is_current"])
        self.assertFalse(any(o["is_current"] for o in options[1:]))
        self.assertEqual(options[0]["drops"], None)  # its cycle already ended: nothing to simulate
        for o in options[1:]:
            self.assertEqual(sum(o["drops"].values()), 10, o["id"])
            self.assertIn(o["water_risk"], ("low", "medium", "high"))
            self.assertEqual(sum(o["season_counts"].values()), o["evaluated"], o["id"])
            self.assertIn(str(o["drops"]["out"]), o["sentence"]["en"])

    def test_scenarios_give_one_result_per_season_for_every_option_in_the_same_order(self):
        scenarios, seasons = self.doc["scenarios"], len(ws.SEASON_YEARS)
        self.assertEqual((scenarios["from_year"], scenarios["to_year"]), (ws.SEASON_YEARS[0], ws.SEASON_YEARS[-1]))
        self.assertEqual([o["id"] for o in scenarios["options"]], [o["id"] for o in self.summary["options"]])
        for option, card in zip(scenarios["options"], self.summary["options"]):
            self.assertEqual(len(option["years"]), seasons if card["drops"] else 0, option["id"])
            self.assertTrue(set(option["years"]) <= {"ok", "tight", "out", None})

    def test_the_yearly_results_agree_with_the_counts_of_a_crop_option(self):
        counts = {c["id"]: c for c in self.summary["options"]}
        for option in self.doc["scenarios"]["options"]:
            card = counts[option["id"]]
            if card["kind"] == "crop" and card["drops"]:
                self.assertEqual(option["years"].count("out"), card["season_counts"]["high_deficit"])

    def test_inputs_are_normalised_ids_and_the_forms_lists_are_closed(self):
        inputs, catalog = self.doc["inputs"], self.doc["catalog"]
        self.assertEqual(inputs["farmer"]["current_crop"], {"crop": "barley", "sowing_day": "06-10"})
        allowed = {c["id"] for c in catalog["history_crops"]}
        for season in inputs["farmer"]["seasons"]:
            self.assertTrue(set(season["crops"]) <= allowed)
            self.assertIn(season["season"], catalog["seasons"])
        self.assertEqual({c["id"] for c in catalog["crops"]}, set(ps.CROP_CHOICES))
        self.assertEqual([r["value"] for r in catalog["ratings"]], [1, 2, 3, 4, 5])
        self.assertEqual(inputs["agronomist"]["soil_test"]["ph"], 6.0)

    def test_the_field_and_site_are_stated(self):
        self.assertEqual((self.summary["field"]["department"], self.summary["field"]["id"]), ("Soriano", "soriano"))
        site = self.doc["site"]
        self.assertTrue(site["soil_calibration"]["current"])
        self.assertEqual(site["climate"]["source"], "nasa_power")
        self.assertEqual(site["climate"]["seasons"], len(ws.SEASON_YEARS))

    def test_the_same_run_gives_the_same_bytes(self):
        with tempfile.TemporaryDirectory() as other:
            export(other)
            self.assertEqual((Path(other) / "frontend.json").read_bytes(), (Path(self.dir.name) / "frontend.json").read_bytes())

    def test_the_field_guide_lists_every_field_with_its_meaning_and_use(self):
        rows = schema.fields()
        self.assertGreater(len(rows), 100)
        self.assertTrue(all(meaning.strip() and used.strip() for _, _, meaning, used in rows))
        paths = {path for path, *_ in rows}
        for expected in ("summary.water.mm", "summary.soil.missing", "summary.options[].drops", "summary.options[].water_risk",
                         "scenarios.options[].years", "inputs.farmer.seasons[].rating", "catalog.ratings[].value",
                         "status.values_by_status.{name}"):
            self.assertIn(expected, paths)
        self.assertEqual(dict((p, k) for p, k, *_ in rows)["summary.options[].sentence"], "text")
        self.assertIn("«Tu campo hoy", dict((p, u) for p, _, _, u in rows)["summary.water.mm"])
        self.assertTrue((Path(self.dir.name) / "frontend.fields.md").exists())

    def test_the_schema_file_written_is_the_one_the_code_builds(self):
        written = json.loads((Path(self.dir.name) / "frontend.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(written, self.schema)


class CommittedFiles(unittest.TestCase):
    """The schema, the field guide and the example the frontend developers read must not drift from the code."""

    def setUp(self):
        if not (REPO / "schema").is_dir():
            self.skipTest("no schema/ folder next to the sources")

    def test_the_committed_schema_and_field_guide_are_current(self):
        hint = "regenerate with: xmart-analysis export --out schema --now " + NOW + " and rename frontend.json to frontend.example.json"
        self.assertEqual((REPO / "schema" / "frontend.schema.json").read_text(encoding="utf-8"), schema.dumps(), hint)
        self.assertEqual((REPO / "schema" / "frontend.fields.md").read_text(encoding="utf-8"), schema.markdown(), hint)

    def test_the_committed_example_is_current_and_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            fresh = export(folder)
        committed = json.loads((REPO / "schema" / "frontend.example.json").read_text(encoding="utf-8"))
        self.assertEqual(schema_check.problems(committed, schema.build(), schema.build()), [])
        # the example carries what a trained registry changes: the learning block, the starting water and the options' drops (their numbers depend on
        # the libraries that trained it, so only their shape is checked here; `tests/test_frontend_learning.py` trains one and checks them);
        # everything else must be exactly what the code produces
        for doc in (committed, fresh):
            doc["learning"] = doc["status"]["simulated_inputs"] = doc["summary"]["water"] = doc["summary"]["options"] = None
        self.assertEqual(committed, fresh, "regenerate with the command above")

    def test_the_committed_example_shows_the_learning_block_filled(self):
        committed = json.loads((REPO / "schema" / "frontend.example.json").read_text(encoding="utf-8"))
        self.assertTrue(committed["learning"]["simulated"])
        self.assertEqual([m["id"] for m in committed["learning"]["models"]], ["B", "A", "C"])
        self.assertIn("training_panel", committed["status"]["simulated_inputs"])


class Command(unittest.TestCase):
    def test_a_scenario_with_an_impossible_reading_leaves_the_error_document_and_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            scenario = json.loads(cli.DEMO.read_text(encoding="utf-8"))
            scenario["readings"] = [{"sensor_id": "node-01", "moisture": 2048, "sensor_type": "capacitive", "received_at": "2026-11-14T10:30:00Z"}]
            path = Path(folder) / "bad.json"
            path.write_text(json.dumps(scenario), encoding="utf-8")
            self.assertEqual(cli.main(["export", str(path), "--out", folder, "--now", NOW]), 1)
            doc = json.loads((Path(folder) / "frontend.json").read_text(encoding="utf-8"))
            self.assertEqual(schema_check.problems(doc, schema.build_error(), schema.build_error()), [])
            self.assertEqual((doc["status"]["mode"], doc["status"]["error"]["code"], doc["status"]["error"]["field"]),
                             ("error", "moisture_out_of_range", "volumetric_moisture"))
            self.assertEqual(doc["generated_at"], NOW)
            self.assertNotIn("summary", doc)

    def test_an_unexpected_failure_is_reported_as_an_internal_error_without_its_text(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(cli, "frontend_document", side_effect=KeyError("secret")):
            self.assertEqual(cli.main(["export", "--out", folder, "--now", NOW]), 1)
            error = json.loads((Path(folder) / "frontend.json").read_text(encoding="utf-8"))["status"]["error"]
            self.assertEqual((error["code"], error["field"]), ("internal_error", None))
            self.assertNotIn("secret", json.dumps(error))

    def test_the_generation_time_is_the_one_given(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(datetime.fromisoformat(export(folder)["generated_at"]), datetime.fromisoformat(NOW))


class Builder(unittest.TestCase):
    def test_dumps_ends_with_a_newline_and_keeps_accents(self):
        text = payload.dumps({"a": "Maíz"})
        self.assertTrue(text.endswith("\n"))
        self.assertIn("Maíz", text)


if __name__ == "__main__":
    unittest.main()
