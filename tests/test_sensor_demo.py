"""The demo runs on the sensor series and says it is a demo: the state the scenarios start from, the badge and the error document."""

import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import schema_check
from xmart_analysis import cli
from xmart_analysis.engine import context as engine_context
from xmart_analysis.engine import sensor_series, sensor_sources, tables
from xmart_analysis.frontend import payload, schema
from xmart_analysis.worker.adapters.files import load_scenario
from xmart_analysis.worker.adapters.memory import MemoryReadings, MemoryStore
from xmart_analysis.worker.domain import Reading
from xmart_analysis.worker.mapping.sensor import daily_history, to_sensor_info

NOW = "2026-11-14T10:30:00+00:00"
REPO = Path(__file__).resolve().parents[1]


def at(day, hour=12):
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)


class History(unittest.TestCase):
    def test_a_day_keeps_its_last_reading_and_the_days_come_oldest_first(self):
        readings = [Reading("f", "n", 0.30, "capacitive", at(date(2026, 1, 2))), Reading("f", "n", 0.20, "capacitive", at(date(2026, 1, 1), 6)),
                    Reading("f", "n", 0.22, "capacitive", at(date(2026, 1, 1), 18))]
        self.assertEqual(daily_history(readings), [{"date": "2026-01-01", "moisture": 0.22}, {"date": "2026-01-02", "moisture": 0.30}])

    def test_one_day_of_readings_is_not_a_series(self):
        one = Reading("f", "n", 0.25, "simulated", at(date(2026, 1, 1)))
        self.assertNotIn("history", to_sensor_info(one, at(date(2026, 1, 1)), [one]))
        two = [one, Reading("f", "n", 0.26, "simulated", at(date(2026, 1, 2)))]
        self.assertEqual(len(to_sensor_info(two[1], at(date(2026, 1, 2)), two)["history"]), 2)

    def test_the_store_returns_the_last_readings_oldest_first(self):
        store = MemoryStore()
        for i in range(5):
            store.add_reading(Reading("f", "n", 0.2 + i / 100, "simulated", at(date(2026, 1, 1) + timedelta(days=i))))
        store.add_reading(Reading("other", "n", 0.5, "simulated", at(date(2026, 1, 9))))
        history = MemoryReadings(store).history("f", 3)
        self.assertEqual([r.received_at.day for r in history], [3, 4, 5])


class StateFromTheSeries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = engine_context.build_context()
        cls.readings = sensor_series.load()

    def info(self, readings):
        days = [{"date": d.isoformat(), "moisture": v} for d, v in sorted(readings.items())]
        last = max(readings)
        return {"source": "x", "is_simulated": True, "volumetric_moisture": readings[last], "timestamp": None, "warnings": [], "history": days}

    def test_the_state_is_the_models_corrected_by_the_whole_series_and_keeps_the_last_reading(self):
        info = sensor_sources.apply_history(self.info(self.readings), self.context)
        last = max(self.readings)
        self.assertEqual(info["raw_moisture"], self.readings[last])
        self.assertEqual(info["volumetric_moisture"], sensor_series.assimilate(self.context, self.readings)[last])
        self.assertNotEqual(info["volumetric_moisture"], info["raw_moisture"])
        self.assertEqual(info["series"]["days"], 365)
        self.assertEqual(info["series"]["period"], [min(self.readings).isoformat(), last.isoformat()])

    def test_without_a_series_the_reading_is_used_as_it_is(self):
        info = {"volumetric_moisture": 0.25, "warnings": []}
        self.assertIs(sensor_sources.apply_history(info, self.context), info)

    def test_a_series_beyond_the_climate_falls_back_to_the_reading_and_says_so(self):
        beyond = {max(self.context["weather"]) + timedelta(days=d): 0.25 for d in (1, 2)}
        info = sensor_sources.apply_history(self.info(beyond), self.context)
        self.assertEqual(info["volumetric_moisture"], 0.25)
        self.assertIn("series_beyond_climate", info["warnings"])
        self.assertNotIn("series", info)


class Demo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = cli.frontend_document(None, NOW)
        cls.water = cls.doc["summary"]["water"]

    def test_the_demo_scenario_carries_the_whole_simulated_year(self):
        _, store = load_scenario(cli.DEMO)
        self.assertEqual(len(store.readings), tables.constant("sensor_days"))
        self.assertTrue(all(r.sensor_type == "simulated" for r in store.readings))

    def test_the_demo_says_it_is_a_demo_and_what_is_simulated(self):
        status = self.doc["status"]
        self.assertEqual((status["mode"], status["simulated_inputs"], status["simulated_reading"]), ("demo", ["sensor_readings"], True))
        self.assertIn("simulados", status["badge"]["es"])
        self.assertIn("Demo", status["badge"]["en"])

    def test_the_water_the_scenarios_start_from_comes_from_the_series(self):
        series = self.water["series"]
        self.assertEqual(series["method"], "state_correction")
        self.assertEqual(len(series["history"]), series["days"])
        self.assertAlmostEqual(self.water["volumetric_moisture"], series["history"][-1]["modeled"], places=3)
        self.assertEqual(self.water["reading_moisture"], series["history"][-1]["reading"])
        self.assertEqual(self.water["updated_at"][:10], series["period"][1])

    def test_the_five_states_of_the_panel_are_described_with_both_languages(self):
        modes = self.doc["catalog"]["modes"]
        self.assertEqual([m["id"] for m in modes], ["demo", "live", "pending", "error", "offline"])
        for mode in modes:
            for key in ("badge", "meaning"):
                self.assertTrue(mode[key]["en"].strip() and mode[key]["es"].strip())

    def test_a_measured_reading_alone_is_live_without_a_series(self):
        with tempfile.TemporaryDirectory() as folder:
            scenario = json.loads(cli.DEMO.read_text(encoding="utf-8"))
            scenario["readings"] = [{"sensor_id": "node-01", "moisture": 0.27, "sensor_type": "capacitive", "received_at": "2026-11-14T09:00:00Z"}]
            path = Path(folder) / "live.json"
            path.write_text(json.dumps(scenario), encoding="utf-8")
            doc = cli.frontend_document(str(path), NOW)
        self.assertEqual((doc["status"]["mode"], doc["status"]["simulated_inputs"]), ("live", []))
        self.assertIsNone(doc["summary"]["water"]["series"])
        self.assertEqual(doc["summary"]["water"]["volumetric_moisture"], 0.27)
        self.assertEqual(schema_check.problems(doc, schema.build(), schema.build()), [])


class ErrorDocument(unittest.TestCase):
    ERROR = {"code": "climate_gap", "field": "climate", "message": "Missing model values before the last valid day: ['2026-03-04']", "details": {}}

    def document(self):
        return payload.build_error(self.ERROR, datetime.fromisoformat(NOW))

    def test_it_follows_its_schema_and_every_field_is_documented(self):
        root = schema.build_error()
        self.assertEqual(schema_check.problems(self.document(), root, root), [])
        self.assertEqual(schema_check.missing(root, "description"), [])
        self.assertEqual(schema_check.missing(root, "x-used-in"), [])

    def test_the_committed_files_are_current(self):
        if not (REPO / "schema").is_dir():
            self.skipTest("no schema/ folder next to the sources")
        self.assertEqual((REPO / "schema" / "frontend.error.schema.json").read_text(encoding="utf-8"), schema.dumps_error())
        self.assertEqual((REPO / "schema" / "frontend.error.example.json").read_text(encoding="utf-8"), payload.dumps(self.document()),
                         "regenerate the example from payload.build_error")


if __name__ == "__main__":
    unittest.main()
