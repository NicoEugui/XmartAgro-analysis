"""The stores: rows are only added, loading twice changes nothing, and training reads what the stores hold."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from xmart_analysis import cli

HAVE_LEARN = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "sklearn"))
if HAVE_LEARN:
    from xmart_analysis.learning import examples, ingest, training
    from xmart_analysis.learning.stores import AppendOnlyTable, ExamplesStore, SeriesStore


@unittest.skipUnless(HAVE_LEARN, "numpy, scipy and scikit-learn are not installed")
class Table(unittest.TestCase):
    def table(self, folder):
        return AppendOnlyTable(Path(folder) / "t.jsonl", ("a", "b"))

    def test_new_rows_are_added_and_known_ones_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            table = self.table(folder)
            self.assertEqual(table.rows(), [])
            self.assertEqual(table.append([{"a": 1, "b": "x", "v": 1}, {"a": 1, "b": "y", "v": 2}]), (2, 0))
            self.assertEqual(table.append([{"a": 1, "b": "x", "v": 1}, {"a": 2, "b": "x", "v": 3}]), (1, 1))
            self.assertEqual(len(table), 3)

    def test_a_stored_row_is_never_edited(self):
        with tempfile.TemporaryDirectory() as folder:
            table = self.table(folder)
            table.append([{"a": 1, "b": "x", "v": "first"}])
            self.assertEqual(table.append([{"a": 1, "b": "x", "v": "changed"}]), (0, 1))
            self.assertEqual(table.rows(), [{"a": 1, "b": "x", "v": "first"}])

    def test_the_rows_survive_a_new_instance_and_a_repeated_batch_changes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            batch = [{"a": i, "b": "x", "v": i} for i in range(5)]
            self.table(folder).append(batch)
            before = (Path(folder) / "t.jsonl").read_text(encoding="utf-8")
            self.assertEqual(self.table(folder).append(batch), (0, 5))
            self.assertEqual((Path(folder) / "t.jsonl").read_text(encoding="utf-8"), before)

    def test_a_row_without_its_key_is_an_error_and_nothing_is_written(self):
        with tempfile.TemporaryDirectory() as folder:
            table = self.table(folder)
            with self.assertRaises(KeyError):
                table.append([{"a": 1, "b": "x"}, {"a": 2}])
            self.assertEqual(table.rows(), [])

    def test_the_series_store_filters_by_field_and_dates(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SeriesStore(folder)
            store.append("daily", [{"field_id": f, "date": d} for f in ("f1", "f2") for d in ("2026-01-01", "2026-01-02", "2026-01-03")])
            self.assertEqual(len(store.rows("daily")), 6)
            self.assertEqual([r["date"] for r in store.rows("daily", "f1", "2026-01-02", "2026-01-03")], ["2026-01-02", "2026-01-03"])
            self.assertEqual(store.rows("nodes"), [])

    def test_the_examples_store_keeps_the_three_models_apart(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ExamplesStore(folder)
            store.append("B", [{"field_id": "f", "date": "2026-01-01"}])
            store.append("A", [{"field_id": "f", "producer_id": None, "season": "2025/26", "crop": "maize"}])
            self.assertEqual((len(store.rows("A")), len(store.rows("B")), len(store.rows("C"))), (1, 1, 0))


@unittest.skipUnless(HAVE_LEARN, "numpy, scipy and scikit-learn are not installed")
class Ingest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = examples.Panel()
        cls.folder = tempfile.TemporaryDirectory()
        cls.series, cls.store, cls.loaded = training.load_stores(cls.folder.name, cls.panel)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_every_field_has_its_whole_nasa_record_and_every_node_a_year_of_readings(self):
        daily, nodes = self.series.rows("daily"), self.series.rows("nodes")
        fields = {r["field_id"] for r in daily}
        self.assertEqual(len(fields), 8)
        self.assertEqual({len([r for r in daily if r["field_id"] == f]) for f in fields}, {14746})
        self.assertEqual(len({r["node_id"] for r in nodes}), 16)
        self.assertTrue(all(r["simulated"] for r in nodes))

    def test_the_satellite_is_flagged_real_only_at_the_two_real_fields(self):
        flags = {r["field_id"]: r["satellite_simulated"] for r in self.series.rows("daily")}
        self.assertEqual({f for f, simulated in flags.items() if not simulated}, {"soriano", "la_estanzuela"})

    def test_loading_the_same_panel_again_adds_nothing(self):
        again = training.load_stores(self.folder.name, self.panel)[2]
        for kind in again.values():
            for added, skipped in kind.values():
                self.assertEqual(added, 0)
                self.assertGreater(skipped, 0)

    def test_the_examples_of_b_are_the_field_mean_of_its_calibrated_nodes_on_days_with_a_satellite_value(self):
        daily = {(r["field_id"], r["date"]): r for r in self.series.rows("daily")}
        nodes = {}
        for r in self.series.rows("nodes"):
            nodes.setdefault((r["field_id"], r["date"]), []).append(r["calibrated_moisture"])
        rows = self.store.rows("B")
        self.assertEqual(len(rows), sum(1 for k in nodes if daily[k]["smap_rootzone"] is not None))
        for r in rows[::400]:
            key = (r["field_id"], r["date"])
            self.assertAlmostEqual(r["sensor"], sum(nodes[key]) / len(nodes[key]), places=4)
            self.assertEqual(r["smap"], daily[key]["smap_rootzone"])

    def test_the_examples_have_the_rows_the_direct_build_gives(self):
        direct = training.datasets(self.panel)
        self.assertEqual({k: len(v) for k, v in direct.items()}, {k: len(self.store.rows(k)) for k in "ABC"})

    def test_new_data_is_appended_to_what_is_there(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ExamplesStore(folder)
            store.append("A", self.store.rows("A")[:10])
            row = {"field_id": "soriano", "producer_id": "p99", "season": "2026/27", "crop": "maize", "model_stress": 0.2, "class": "good",
                   "simulated": False, "source": "producer_form"}
            self.assertEqual(store.append("A", [row]), (1, 0))
            self.assertEqual(len(store.rows("A")), 11)
            self.assertFalse(store.rows("A")[-1]["simulated"])  # a real row sits next to the simulated ones, marked

    def test_the_ingest_command_loads_and_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(cli.main(["ingest", "--out", folder]), 0)
            self.assertTrue((Path(folder) / "series" / "daily.jsonl").exists())
            self.assertTrue((Path(folder) / "examples" / "A.jsonl").exists())

    def test_training_reads_the_store_and_a_second_training_loads_nothing_new(self):
        with tempfile.TemporaryDirectory() as folder:
            first = training.train(folder, "2026-11-15", self.panel, only=["B"])
            second = training.train(folder, "2026-11-16", self.panel, only=["B"])
            self.assertEqual(first["data"]["B"], len(ExamplesStore(Path(folder) / "examples").rows("B")))
            self.assertEqual(second["data"], first["data"])
            self.assertEqual(second["loaded"]["examples"]["B"][0], 0)
            self.assertEqual(json.loads((Path(folder) / "registry.json").read_text(encoding="utf-8"))[-1]["trained_on"], "2026-11-16")


if __name__ == "__main__":
    unittest.main()
