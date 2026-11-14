import logging
import unittest
from datetime import datetime, timedelta, timezone


from xmart_analysis.engine import water_scenarios as ws
from xmart_analysis.worker.adapters.engine import EngineAnalyzer
from xmart_analysis.worker.adapters.memory import (MemoryInputs, MemoryJobQueue, MemoryReadings, MemoryResults,
                                             MemoryStore)
from xmart_analysis.worker.application import RunAnalysis
from xmart_analysis.worker.config import Settings
from xmart_analysis.worker.domain import Reading
from xmart_analysis.worker.mapping import inputs as mi
from xmart_analysis.worker.mapping.sensor import to_sensor_info
from xmart_analysis.worker.worker import Worker
from xmart_analysis.engine.errors import EngineError

logging.disable(logging.CRITICAL)
COMPARISON = ({"kind": "crop", "crop": "soybean_2nd", "sowing": "12-10"}, {"kind": "crop", "crop": "maize_2nd", "sowing": "12-15"},
              {"kind": "rotation", "rotation": "survey_03"})
NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
ANALYZER = EngineAnalyzer()
FARMER = {"crop": "Cebada", "sowing_date": "2026-06-10",
          "seasons": [{"season": "2025/26", "crop": "Cebada + soja de segunda", "rating": 3, "yield_kg_ha": None},
                      {"season": "2024/25", "crop": "Trigo", "rating": 4, "yield_kg_ha": 3100}]}
AGRONOMIST = {"soil_test": {"date": "2026-05", "om_pct": 3.4, "p_bray_ppm": 12, "ph": 5.8}, "erosion_t_ha_yr": 6.2,
              "soil_type": {"coneat": "10.8b", "name": "Brunosol", "confirmed": True}}


def reading(moisture=0.24, sensor_type="capacitive", at=NOW, field="f1"):
    return Reading(field, "node-01", moisture, sensor_type, at)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.settings = Settings(max_attempts=2, comparison=COMPARISON)
        self.clock = lambda: NOW
        self.run = RunAnalysis(MemoryReadings(self.store), MemoryInputs(self.store), MemoryResults(self.store), ANALYZER,
                               self.settings, self.clock)
        self.queue = MemoryJobQueue(self.store, timedelta(minutes=15))
        self.worker = Worker(self.queue, self.run, self.settings, self.clock, sleep=lambda s: None)

    def seed(self, **kw):
        self.store.add_reading(reading(**kw))
        self.store.inputs["f1"] = {"farmer": FARMER, "agronomist": AGRONOMIST}


class InputMapping(unittest.TestCase):
    def test_crop_names_ignore_case_and_accents(self):
        self.assertEqual(mi.crop_id("  MAÍZ de Segunda "), "maize_2nd")
        self.assertEqual(mi.crop_id("soybean_2nd"), "soybean_2nd")
        self.assertIsNone(mi.crop_id("quinoa"))

    def test_a_season_with_two_crops_is_split_and_unknown_names_are_reported(self):
        notes = []
        self.assertEqual(mi.crop_ids("Cebada + soja de segunda", notes, "x"), ["barley", "soybean_2nd"])
        mi.crop_ids("Trigo, quinoa", notes, "x")
        self.assertEqual([n["received"] for n in notes], ["quinoa"])

    def test_answers_follow_the_engine_vocabulary(self):
        answers, notes = mi.to_answers({"farmer": FARMER, "agronomist": AGRONOMIST}, reading(), Settings().comparison)
        self.assertEqual(answers["current_crop"], {"crop": "barley", "sowing": "06-10"})
        self.assertEqual(answers["reading_date"], "11-14")
        self.assertEqual(answers["agronomist"]["soil_type"], "CONEAT 10.8b, Brunosol")
        self.assertEqual(answers["past_seasons"][0]["crops"], ["barley", "soybean_2nd"])
        self.assertEqual(notes, ())

    def test_missing_inputs_still_produce_valid_answers(self):
        answers, _ = mi.to_answers(None, reading(), Settings().comparison)
        self.assertNotIn("current_crop", answers)
        self.assertEqual(answers["past_seasons"], [])


class SensorMapping(unittest.TestCase):
    def test_a_stored_reading_is_flagged_for_unknown_depth_and_age(self):
        info = to_sensor_info(reading(at=NOW - timedelta(hours=30)), NOW)
        self.assertEqual(info["source"], "backend_api_sensor")
        self.assertFalse(info["is_simulated"])
        self.assertEqual(set(info["warnings"]), {"depth_unknown", "stale_reading"})

    def test_a_simulated_node_stays_simulated(self):
        self.assertTrue(to_sensor_info(reading(sensor_type="simulated"), NOW)["is_simulated"])

    def test_a_raw_adc_value_is_rejected_instead_of_interpreted(self):
        with self.assertRaises(EngineError) as ctx:
            to_sensor_info(reading(moisture=2048), NOW)
        self.assertEqual(ctx.exception.field, "volumetric_moisture")


class UseCase(Fixture):
    def test_it_computes_and_saves_a_results_document(self):
        self.seed()
        outcome = self.run("f1")
        doc = self.store.results["f1"]
        self.assertEqual(outcome.status, "computed")
        self.assertEqual({"summary", "scenarios", "analysis", "inputs_hash"} <= set(doc), True)
        self.assertEqual(set(doc["analysis"]), {"en", "es"})

    def test_unchanged_inputs_are_not_recomputed_and_changed_ones_are(self):
        self.seed()
        self.run("f1")
        self.assertEqual(self.run("f1").status, "unchanged")
        self.store.add_reading(reading(moisture=0.30, at=NOW + timedelta(minutes=1)))
        self.assertEqual(self.run("f1").status, "computed")

    def test_a_field_without_readings_fails_with_a_clear_code(self):
        with self.assertRaises(EngineError) as ctx:
            self.run("nobody")
        self.assertEqual(ctx.exception.code, "no_reading")


class ResultsDocument(Fixture):
    def setUp(self):
        super().setUp()
        self.seed()
        self.run("f1")
        self.doc = self.store.results["f1"]

    def test_drops_use_the_api_vocabulary_and_add_to_ten(self):
        for option in self.doc["summary"]["options"]:
            if option["drops"]:
                self.assertEqual(set(option["drops"]), {"ok", "tight", "out"})
                self.assertEqual(sum(option["drops"].values()), 10)
                self.assertIn(option["water_risk"], {"low", "medium", "high"})

    def test_an_ended_cycle_has_no_drops_and_says_why(self):
        current = next(o for o in self.doc["summary"]["options"] if o["is_current"])
        self.assertIsNone(current["drops"])
        self.assertIn("ciclo", current["sentence"])

    def test_scenarios_list_one_class_per_historical_season_for_crops(self):
        by_id = {o["id"]: o["years"] for o in self.doc["scenarios"]["options"]}
        self.assertEqual(len(by_id["soybean_2nd@12-10"]), len(ws.SEASON_YEARS))
        self.assertTrue(set(by_id["soybean_2nd@12-10"]) <= {"ok", "tight", "out"})
        self.assertEqual(len(by_id["survey_03"]), len(ws.SEASON_YEARS))  # a rotation season is classed by its mean stress

    def test_nothing_unmeasured_is_claimed(self):
        soil = self.doc["summary"]["soil"]
        self.assertIsNone(soil["state"])
        self.assertEqual(self.doc["summary"]["water"]["mm_status"], "derived_from_assumptions")
        self.assertFalse(self.doc["summary"]["water"]["is_simulated"])
        self.assertTrue(all(o["soil_effect"] is None for o in self.doc["summary"]["options"]))


class WorkerLoop(Fixture):
    def test_a_job_is_done_and_older_duplicates_are_superseded(self):
        self.seed()
        self.store.request_job("f1", NOW - timedelta(seconds=2))
        self.store.request_job("f1", NOW - timedelta(seconds=1))
        self.assertEqual(self.worker.run_until_idle(), 1)
        self.assertEqual([j["status"] for j in self.store.jobs], ["done", "done"])
        self.assertEqual(self.store.jobs[1]["error"], {"code": "superseded"})

    def test_an_engine_error_fails_the_job_with_its_structured_error(self):
        self.store.request_job("ghost", NOW)
        self.worker.run_once()
        job = self.store.jobs[0]
        self.assertEqual((job["status"], job["error"]["code"]), ("failed", "no_reading"))

    def test_an_unexpected_crash_is_retried_then_failed(self):
        self.seed()
        self.store.request_job("f1", NOW)
        self.worker.run = lambda field: 1 / 0
        self.worker.run_once()
        self.assertEqual(self.store.jobs[0]["status"], "pending")
        self.worker.run_once()
        self.assertEqual((self.store.jobs[0]["status"], self.store.jobs[0]["error"]["code"]), ("failed", "internal_error"))

    def test_a_job_stuck_in_running_is_reclaimed_after_the_stale_window(self):
        self.seed()
        job = self.store.request_job("f1", NOW - timedelta(hours=1))
        job.update(status="running", claimed_at=NOW - timedelta(minutes=30), attempts=1)
        self.assertEqual(self.worker.run_until_idle(), 1)
        self.assertEqual(job["status"], "done")

    def test_an_idle_queue_returns_without_work(self):
        self.assertFalse(self.worker.run_once())


if __name__ == "__main__":
    unittest.main()
