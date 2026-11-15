"""The charts the frontend draws: well-formed, honest about what is simulated, and the same numbers the experiment log plots."""

import json
import unittest
from datetime import datetime

import fixtures
import schema_check
from xmart_analysis import cli
from xmart_analysis.frontend import charts, schema
from xmart_analysis.worker.mapping.results import to_results

NOW = "2026-11-14T10:30:00+00:00"


class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.charts = charts.build()

    def test_every_series_has_one_value_per_position_and_the_ids_are_unique(self):
        ids = [c["id"] for c in self.charts]
        self.assertEqual(len(ids), len(set(ids)))
        for chart in self.charts:
            positions = len(chart["x"]["values"])
            self.assertGreater(positions, 0, chart["id"])
            for series in chart["series"]:
                self.assertEqual(len(series["values"]), positions, (chart["id"], series["id"]))
            for key in ("names", "tags"):
                if chart["x"][key] is not None:
                    self.assertEqual(len(chart["x"][key]), positions, (chart["id"], key))

    def test_every_figure_of_the_experiment_log_has_charts(self):
        figures = {c["figure"] for c in self.charts}
        self.assertEqual(figures, {"sowing", "survey", "smap", "ndvi", "imerg", "rain_decision", "sensor", "sensor_windows", "sensor_recalibration"})

    def test_what_comes_from_a_simulation_says_so_and_what_comes_from_nasa_data_does_not(self):
        for chart in self.charts:
            if chart["group"] == "sensor" or chart["id"].startswith("sowing"):
                self.assertTrue(chart["simulated"], chart["id"])
            if chart["source"] in ("smap_l3", "modis_ndvi", "gpm_imerg", "producer_survey"):
                self.assertFalse(chart["simulated"], chart["id"])
        self.assertTrue(all(c["source"] == "simulated_sensor" for c in self.charts if c["group"] == "sensor"))

    def test_stacked_bars_count_whole_seasons(self):
        for chart in self.charts:
            if chart["stacked"]:
                totals = [sum(series["values"][i] for series in chart["series"]) for i in range(len(chart["x"]["values"]))]
                self.assertTrue(all(isinstance(t, int) and t > 0 for t in totals), chart["id"])
                # the same seasons under every rain source or reading; a sowing date can lose a season whose window leaves the record
                self.assertLessEqual(max(totals) - min(totals), 0 if chart["id"].startswith(("rain_", "sowing_reading")) else 2, (chart["id"], totals))

    def test_the_sensor_series_is_the_simulated_year_and_has_a_reading_per_day(self):
        series = next(c for c in self.charts if c["id"] == "sensor_series")
        self.assertEqual(len(series["x"]["values"]), 365)
        self.assertEqual([s["id"] for s in series["series"]], ["readings", "truth", "open_loop", "with_sensor"])

    def test_the_charts_are_language_neutral_texts_and_json(self):
        text = json.dumps(self.charts, ensure_ascii=False)
        self.assertNotIn("NaN", text)
        for chart in self.charts:
            self.assertEqual(set(chart["title"]), {"key", "en", "es"})

    def test_a_caller_cannot_change_what_the_next_one_gets(self):
        first = charts.build()
        first[0]["series"][0]["values"][0] = -1
        self.assertNotEqual(charts.build()[0]["series"][0]["values"][0], -1)


class InTheDocuments(unittest.TestCase):
    def test_the_frontend_file_carries_them_and_follows_the_schema(self):
        doc = cli.frontend_document(None, NOW)
        self.assertEqual(doc["charts"], charts.build())
        self.assertEqual(schema_check.problems(doc, schema.build(), schema.build()), [])

    def test_the_results_document_carries_them_in_the_language_of_the_panel(self):
        from xmart_analysis.engine import platform_session as ps
        session = ps.build_session(fixtures.default_answers())
        results = to_results("f1", session, "hash", datetime.fromisoformat(NOW), "v", "es", [])
        self.assertEqual(len(results["charts"]), len(charts.build()))
        self.assertIsInstance(results["charts"][0]["title"], str)


if __name__ == "__main__":
    unittest.main()
