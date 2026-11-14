"""The experiment log: the numbers each figure plots are the numbers in its table, and the document is complete."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_offline
from xmart_analysis import cli
from xmart_analysis.engine import tables
from xmart_analysis.report import scenario_runs
from xmart_analysis.validation import imerg, rain_sensitivity, survey


NDVI = {"seasons": [{"season": f"20{i:02d}/{i + 1:02d}", "ndvi_dec_mar": 0.5 + i / 100, "soybean_1st_stress": i / 10,
                     "maize_stress": 0.9 - i / 10} for i in range(2, 8)],
        "correlations": {"soybean_1st": {"spearman_ndvi_vs_minus_stress": 0.25, "permutation_p": 0.24},
                         "maize": {"spearman_ndvi_vs_minus_stress": 0.29, "permutation_p": 0.16}},
        "lowest_ndvi_seasons": ["2002/03", "2003/04"], "most_stressed_seasons": ["2007/08"], "overlap": 1, "overlap_expected_by_chance": 0.5}
SMAP = {"depth_note": "note", "periods": {"validation": {"days": 10, "scores": {
    "model": {"spearman": 0.78, "anomaly_r": 0.63}, "smap_l4": {"spearman": 0.77, "anomaly_r": 0.65},
    "rain_index": {"spearman": 0.5, "anomaly_r": 0.65}}}}}


def numbers(figure):
    """Every value a figure plots: scatter points and bar sizes."""
    found = set()
    for ax in figure.axes:
        for collection in ax.collections:
            found.update(float(v) for v in collection.get_offsets().flatten())
        for patch in ax.patches:
            found.update((float(patch.get_height()), float(patch.get_width())))
    return found


def plotted(draw, doc):
    captured = []
    original = __import__("matplotlib.figure", fromlist=["Figure"]).Figure.savefig

    def spy(self, *args, **kwargs):
        captured.append(numbers(self))
        return original(self, *args, **kwargs)

    with tempfile.TemporaryDirectory() as folder, mock.patch("matplotlib.figure.Figure.savefig", spy):
        draw(doc, Path(folder) / "figure.png", "en")
    return captured[0]


@unittest.skipUnless(test_offline.HAVE_MPL, "matplotlib is not installed")
class PlottedValues(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from xmart_analysis.report import experiments
        cls.experiments = experiments
        source = test_offline.ImergValidator
        source.setUpClass()
        cls.docs = {"survey": survey.run(source.ctx), "imerg": imerg.run(source.path, source.ctx),
                    "rain_sensitivity": rain_sensitivity.run(source.path, source.ctx), "ndvi": NDVI, "smap": SMAP,
                    "sowing": scenario_runs.run(source.ctx)}

    @classmethod
    def tearDownClass(cls):
        test_offline.ImergValidator.tearDownClass()

    def test_every_number_in_a_figure_table_is_plotted(self):
        for name, (draw, table) in self.experiments.FIGURES.items():
            with self.subTest(figure=name):
                _, rows = table(self.docs[name])
                values = {float(v) for row in rows for v in row if isinstance(v, (int, float))}
                self.assertTrue(values)
                missing = {v for v in values if not any(abs(v - p) < 1e-9 for p in plotted(draw, self.docs[name]))}
                self.assertEqual(missing, set())

    def test_the_report_has_every_section_and_a_figure_per_experiment(self):
        calibration = json.loads(tables.calibration_path().read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as out:
            frontend = cli.frontend_document(None)
            path = self.experiments.build(self.docs, calibration, frontend, out, {"imerg": str(test_offline.ImergValidator.path)})
            text = path.read_text(encoding="utf-8")
            for name in self.experiments.FIGURES:
                self.assertIn(f"figures/{name}.en.png", text)
                self.assertTrue((Path(out) / "figures" / f"{name}.en.png").exists())
            for heading in ("What happens if a crop is sown", "Data architecture", "Model and calibration", "Integrity checks", "Not validated"):
                self.assertIn(heading, text)
            self.assertIn("consistent", text)
            self.assertIn(tables.manifest()[0]["path"], text)

    def test_the_sowing_grid_covers_every_crop_and_date_and_counts_the_seasons(self):
        doc = self.docs["sowing"]
        self.assertEqual(list(doc["crops"]), list(scenario_runs.CROPS))
        for entry in doc["crops"].values():
            self.assertEqual(len(entry["dates"]), len(scenario_runs.SHIFTS_DAYS))
            for run in entry["dates"]:
                self.assertEqual(sum(run["counts"].values()), run["seasons"])
        self.assertEqual(len(doc["detail"]["seasons"]), doc["crops"][scenario_runs.DETAIL_CROP]["dates"][2]["seasons"])
        self.assertEqual([r["volumetric_moisture"] for r in doc["reading_sensitivity"]["readings"]], list(scenario_runs.READINGS))

    def test_a_missing_validator_leaves_its_section_out(self):
        calibration = json.loads(tables.calibration_path().read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as out:
            path = self.experiments.build({"survey": self.docs["survey"]}, calibration, cli.frontend_document(None), out)
            text = path.read_text(encoding="utf-8")
            self.assertIn("figures/survey.en.png", text)
            self.assertNotIn("figures/smap.en.png", text)

    def test_the_report_command_writes_the_document(self):
        with tempfile.TemporaryDirectory() as out:
            self.assertEqual(cli.main(["report", "--out", out, "--imerg", str(test_offline.ImergValidator.path)]), 0)
            self.assertTrue((Path(out) / "experiments.md").exists())
            self.assertTrue((Path(out) / "figures" / "rain_sensitivity.en.png").exists())


if __name__ == "__main__":
    unittest.main()
