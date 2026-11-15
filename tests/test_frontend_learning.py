"""The `learning` block of the frontend document (schema 3.0): what the published models add, and null when there are none."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

import learned
from xmart_analysis import cli
from xmart_analysis.engine import deficit
from xmart_analysis.frontend import payload, schema
from xmart_analysis.frontend import learning as block

import schema_check

HAVE_LEARN = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "sklearn"))
NOW = "2026-11-14T10:30:00+00:00"


@unittest.skipUnless(HAVE_LEARN, "numpy, scipy and scikit-learn are not installed")
class LearningBlock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = cli.frontend_document(None, NOW, learned.folder())
        cls.learning = cls.doc["learning"]

    def test_the_document_is_version_three_and_follows_the_schema(self):
        self.assertEqual(self.doc["schema_version"], "3.0")
        self.assertEqual(schema_check.problems(json.loads(payload.dumps(self.doc)), schema.build(), schema.build()), [])

    def test_without_a_registry_the_block_is_null_and_nothing_is_adjusted(self):
        plain = cli.frontend_document(None, NOW)
        self.assertIsNone(plain["learning"])
        self.assertEqual(plain["status"]["simulated_inputs"], ["sensor_readings"])
        self.assertEqual(plain["summary"]["water"]["source"], "sensor")
        self.assertIsNone(plain["summary"]["water"]["correction"])
        for option in plain["summary"]["options"]:
            self.assertEqual(option["risk_basis"]["source"], "fixed_cuts")
        for key in ("inputs", "scenarios", "catalog", "charts"):
            self.assertEqual(plain[key], self.doc[key], key)

    def test_with_a_registry_the_start_water_is_the_satellite_corrected_by_b_and_not_a_sensor(self):
        water, plain = self.doc["summary"]["water"], cli.frontend_document(None, NOW)["summary"]["water"]
        self.assertEqual(water["source"], "smap_corrected")
        self.assertEqual(self.doc["status"]["simulated_inputs"], ["training_panel"])
        self.assertEqual(self.doc["status"]["mode"], "demo")
        self.assertEqual(water["correction"]["model"], "B")
        self.assertEqual(water["correction"]["version"], self.learning["models"][0]["version"])
        self.assertNotEqual(water["mm"], plain["mm"])  # what the other fields taught moves the starting water
        self.assertTrue(0 < water["mm"] < water["capacity_mm"])

    def test_the_start_water_is_carried_from_the_last_satellite_day_to_the_last_climate_day(self):
        water = self.doc["summary"]["water"]
        last_climate = self.doc["site"]["climate"]["last_day"]
        self.assertEqual(water["updated_at"][:10], last_climate)
        self.assertLess(water["correction"]["last_satellite_day"], last_climate)
        days = (datetime.fromisoformat(last_climate) - datetime.fromisoformat(water["correction"]["last_satellite_day"])).days
        self.assertEqual(water["series"]["carried_days"], days)

    def test_with_a_registry_the_options_carry_model_a_drops_and_keep_the_fixed_cuts_beside_them(self):
        by_id = {o["id"]: o for o in self.learning["options"]}
        applied = 0
        for option in self.doc["summary"]["options"]:
            basis = option["risk_basis"]
            if option["id"] not in by_id:
                self.assertEqual(basis["source"], "fixed_cuts", option["id"])  # nothing to read: the cycle already ended
                continue
            applied += 1
            read = by_id[option["id"]]
            self.assertEqual((basis["source"], option["drops"], option["water_risk"]), ("model_a", read["of_10"], read["water_risk"]), option["id"])
            self.assertEqual((basis["fixed_cuts_drops"], basis["fixed_cuts_water_risk"]), (read["fixed_cuts_of_10"], read["fixed_cuts_water_risk"]))
            self.assertEqual(basis["model_version"], read["model_version"])
        self.assertGreater(applied, 5)

    def test_the_fixed_cuts_beside_model_a_are_what_the_plain_analysis_shows(self):
        plain = {o["id"]: o for o in cli.frontend_document(None, NOW)["summary"]["options"]}
        for option in self.doc["summary"]["options"]:
            if option["risk_basis"]["source"] == "model_a":
                self.assertEqual(option["risk_basis"]["fixed_cuts_drops"], plain[option["id"]]["drops"], option["id"])

    def test_an_empty_registry_gives_a_null_block(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(block.build(folder, []))
        self.assertIsNone(block.build(None, []))

    def test_it_says_the_models_learned_from_simulated_data(self):
        self.assertTrue(self.learning["simulated"])
        self.assertEqual([m["id"] for m in self.learning["models"]], ["B", "A", "C"])
        for model in self.learning["models"]:
            self.assertEqual((model["state"], model["simulated_data"]), ("published", True))
            self.assertTrue(model["metric"]["better"])  # a model is published only if it beats the fixed rule
            metric = model["metric"]
            self.assertEqual(metric["better"], metric["value"] < metric["fixed_rule"] if metric["lower_is_better"] else metric["value"] > metric["fixed_rule"])

    def test_model_a_reads_every_option_in_ten_seasons_next_to_the_fixed_cuts(self):
        option_ids = {o["id"] for o in self.doc["summary"]["options"]}
        self.assertTrue(self.learning["options"])
        for option in self.learning["options"]:
            self.assertIn(option["id"], option_ids)
            self.assertEqual(sum(option["of_10"].values()), 10)
            self.assertEqual(sum(option["fixed_cuts_of_10"].values()), 10)
            self.assertEqual(option["water_risk"], deficit.water_risk(option["of_10"]))
            self.assertEqual(option["fixed_cuts_water_risk"], deficit.water_risk(option["fixed_cuts_of_10"]))

    def test_model_b_corrects_the_satellite_of_the_demo_field_and_says_it_is_not_a_test(self):
        satellite = self.learning["satellite"]
        self.assertEqual(len(satellite["dates"]), 90)
        self.assertEqual(satellite["dates"], sorted(satellite["dates"]))
        self.assertTrue(satellite["sensor_simulated"] and satellite["in_sample"])
        self.assertEqual({len(satellite[k]) for k in ("satellite", "corrected", "sensor")}, {90})
        self.assertLess(satellite["rmse"]["corrected"], satellite["rmse"]["satellite"])

    def test_model_c_proposes_or_asks_for_each_season_of_the_real_modis_curve_and_nothing_is_confirmed(self):
        history = self.learning["crop_history"]
        self.assertGreater(len(history), 15)
        self.assertEqual([h["season"] for h in history], sorted(h["season"] for h in history))
        for h in history:
            self.assertTrue(0 <= h["confidence"] <= 1)
            self.assertEqual(h["action"], "propose" if h["confidence"] >= 0.6 else "ask")
            self.assertFalse(h["confirmed"])

    def test_the_catalog_has_the_pending_mode_with_its_own_texts(self):
        modes = {m["id"]: m for m in self.doc["catalog"]["modes"]}
        self.assertEqual(list(modes), ["demo", "live", "pending", "error", "offline"])
        self.assertEqual(set(modes["pending"]["badge"]), {"key", "en", "es"})

    def test_the_export_command_writes_the_block_when_it_is_given_a_registry(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(cli.main(["export", "--out", folder, "--now", NOW, "--models", learned.folder()]), 0)
            written = json.loads(open(f"{folder}/frontend.json", encoding="utf-8").read())
            self.assertEqual([m["id"] for m in written["learning"]["models"]], ["B", "A", "C"])


class WithoutTheLearnExtra(unittest.TestCase):
    def test_the_analysis_and_the_export_run_when_numpy_is_missing(self):
        """Models are optional: a plain install (no numpy) exports the same document as before, with the fixed rules."""
        code = ("import sys; sys.modules['numpy'] = None; sys.modules['scipy'] = None\n"
                "from xmart_analysis import cli\n"
                "d = cli.frontend_document(None, 'NOW')\n"
                "assert d['learning'] is None and d['summary']['water']['source'] == 'sensor'\n").replace("NOW", NOW)
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
