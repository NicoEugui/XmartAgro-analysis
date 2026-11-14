"""Running without a database: the CLI, the file adapters and the NASA SMAP validator on synthetic files."""
import csv
import importlib.util
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import fixtures
from xmart_analysis import cli
from xmart_analysis.engine import context
from xmart_analysis.engine import tables
from xmart_analysis.engine.errors import EngineError
from xmart_analysis.validation import files, imerg, ndvi, rain_sensitivity, smap, survey

HAVE_MPL = importlib.util.find_spec("matplotlib") is not None


class OfflineRun(unittest.TestCase):
    def test_the_bundled_demo_runs_and_writes_results_without_figures(self):
        with tempfile.TemporaryDirectory() as out:
            self.assertEqual(cli.main(["run", "--out", out, "--no-figures"]), 0)
            doc = json.loads((Path(out) / "demo-soriano.results.json").read_text(encoding="utf-8"))
            self.assertEqual(set(doc["analysis"]), {"en", "es"})
            self.assertEqual(doc["summary"]["water"]["is_simulated"], True)

    def test_a_second_run_with_the_same_inputs_is_recognised_as_unchanged(self):
        with tempfile.TemporaryDirectory() as out:
            cli.main(["run", "--out", out, "--no-figures"])
            first = (Path(out) / "demo-soriano.results.json").stat().st_mtime_ns
            cli.main(["run", "--out", out, "--no-figures"])
            self.assertEqual(first, (Path(out) / "demo-soriano.results.json").stat().st_mtime_ns)

    @unittest.skipUnless(HAVE_MPL, "matplotlib is not installed")
    def test_the_three_screens_are_drawn_in_both_languages(self):
        with tempfile.TemporaryDirectory() as out:
            cli.main(["run", "--out", out])
            names = {p.name for p in Path(out).glob("*.png")}
            self.assertEqual(len(names), 6, names)

    def test_a_bad_scenario_reports_a_structured_error_and_fails(self):
        with tempfile.TemporaryDirectory() as out:
            scenario = json.loads((cli.DEMO).read_text(encoding="utf-8"))
            scenario["readings"][0]["moisture"] = 2048
            path = Path(out) / "bad.json"
            path.write_text(json.dumps(scenario), encoding="utf-8")
            self.assertEqual(cli.main(["run", str(path), "--out", out, "--no-figures"]), 1)


class NasaFileGuard(unittest.TestCase):
    def write(self, folder, latitude, longitude):
        path = Path(folder) / "file.csv"
        path.write_text(f"Category,ID,Latitude,Longitude,Date\nx,p,{latitude},{longitude},2020-01-01\n", encoding="utf-8")
        return path

    def test_a_file_for_another_point_is_refused_with_both_points_in_the_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(EngineError) as ctx:
                files.check_point(self.write(folder, 0.0, 0.0))
            self.assertEqual(ctx.exception.code, "file_not_at_site")
            self.assertIn("site_point", ctx.exception.details)

    def test_a_file_at_the_site_point_and_a_file_without_coordinates_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            files.check_point(self.write(folder, tables.constant("latitude"), tables.constant("longitude")))
            (Path(folder) / "plain.csv").write_text("Date,value\n2020-01-01,1\n", encoding="utf-8")
            files.check_point(Path(folder) / "plain.csv")

    def test_the_validate_command_reports_the_refusal_and_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = self.write(folder, 0.0, 0.0)
            self.assertEqual(cli.main(["validate", "--out", folder, "--no-figures", "--modis-ndvi", str(bad)]), 1)


class NdviValidator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.ctx = context.build_context()
        cls.stress = ndvi.survey.season_stress("soybean_1st", cls.ctx)
        path = Path(cls.dir.name) / "ndvi.csv"
        with open(path, "w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["Date", "MOD13Q1_061__250m_16_days_NDVI", "MOD13Q1_061__250m_16_days_pixel_reliability"])
            for year in range(2002, 2026):
                season = f"{year}/{(year + 1) % 100:02d}"
                for k in range(8):  # greener when the modelled stress is lower: NDVI built from the model itself
                    day = date(year, 12, 1) + timedelta(days=15 * k)
                    writer.writerow([day.isoformat(), 0.8 - 0.4 * cls.stress[season], 0])
                writer.writerow([date(year, 12, 20).isoformat(), 0.1, 2])  # bad quality: must be ignored
        cls.path = path

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_only_good_quality_composites_are_loaded(self):
        series = ndvi.load(self.path)
        self.assertEqual(len(series), 24 * 8)
        self.assertTrue(all(v > 0.3 for _, v in series))

    def test_ndvi_built_from_the_stress_agrees_perfectly_with_it(self):
        doc = ndvi.run(self.path, self.ctx)
        self.assertEqual(len(doc["seasons"]), 24)
        self.assertEqual(doc["correlations"]["soybean_1st"]["spearman_ndvi_vs_minus_stress"], 1.0)
        self.assertGreaterEqual(doc["overlap"], ndvi.TOP - 1)  # NDVI is rounded to 3 decimals, so ties can swap the sixth season

    def test_chance_overlap_is_reported_next_to_the_overlap(self):
        doc = ndvi.run(self.path, self.ctx)
        self.assertEqual(doc["overlap_expected_by_chance"], round(ndvi.TOP * ndvi.TOP / 24, 1))


class ImergValidator(unittest.TestCase):
    """A Giovanni-shaped file built from the POWER rain itself, so the agreement must be perfect."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.ctx = context.build_context()
        cls.path = Path(cls.dir.name) / "imerg.csv"
        cls.write(cls.path, "-58.05,-33.35,-58.05,-33.35")

    @classmethod
    def write(cls, path, box):
        weather = cls.ctx["weather"]
        lines = ["Title:,\"Time Series, Area-Averaged of Daily mean precipitation rate\"", "User Start Date:,1998-01-01T00:00:00Z",
                 f"Data Bounding Box:,\"{box}\"", "Fill Value (mean_GPM_3IMERGDF_07_precipitation):, -9999.9", "",
                 "time, mean_GPM_3IMERGDF_07_precipitation"]
        for day in sorted(weather):
            if date(1998, 1, 1) <= day <= date(2020, 12, 31):
                lines.append(f"{day},{-9999.9 if day == date(2000, 1, 5) else weather[day]['PRECTOTCORR']}")
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_fill_values_are_dropped_and_the_cell_is_read_from_the_header(self):
        series = imerg.load(self.path)
        self.assertNotIn(date(2000, 1, 5), series)
        self.assertIn(date(2000, 1, 6), series)

    def test_the_same_rain_agrees_perfectly_and_reports_the_period(self):
        doc = imerg.run(self.path, self.ctx)
        self.assertEqual((doc["rain"]["daily_r"], doc["rain"]["monthly_r"], doc["rain"]["season_dec_mar_r"]), (1.0, 1.0, 1.0))
        self.assertEqual(doc["period"], ["1998-01-01", "2020-12-31"])
        self.assertEqual(doc["driest_seasons"]["imerg"], doc["driest_seasons"]["power"])

    def test_a_cell_that_is_not_the_site_is_refused(self):
        other = Path(self.dir.name) / "other.csv"
        self.write(other, "-60.05,-30.35,-60.05,-30.35")
        with self.assertRaises(EngineError) as ctx:
            imerg.load(other)
        self.assertEqual(ctx.exception.code, "file_not_at_site")

    @unittest.skipUnless(HAVE_MPL, "matplotlib is not installed")
    def test_validate_draws_the_imerg_figure_in_both_languages(self):
        with tempfile.TemporaryDirectory() as out:
            self.assertEqual(cli.main(["validate", "--out", out, "--imerg", str(self.path)]), 0)
            names = {p.name for p in Path(out).glob("*.png")}
            self.assertTrue({"validation_imerg.en.png", "validation_imerg.es.png",
                             "validation_rain_sensitivity.en.png", "validation_rain_sensitivity.es.png"} <= names)

    def test_the_same_rain_changes_nothing_in_the_sensitivity(self):
        doc = rain_sensitivity.run(self.path, self.ctx)
        for crop in doc["crops"].values():
            self.assertEqual((crop["spearman_between_sources"], crop["mean_abs_difference"]), (1.0, 0.0))
            self.assertEqual(crop["high_deficit_seasons"]["power"], crop["high_deficit_seasons"]["imerg"])
        for shares in doc["rotations_high_deficit_share"].values():
            self.assertEqual(shares["power"], shares["imerg"])

    def test_only_the_days_with_imerg_rain_are_used(self):
        series = imerg.load(self.path)
        ctx = rain_sensitivity.restricted_context(self.ctx, series, "imerg")
        self.assertEqual(set(ctx["weather"]), set(series))
        self.assertEqual(set(ctx["et0"]), set(series))


class SurveyDataset(unittest.TestCase):
    def test_the_survey_tables_are_consistent_and_cite_their_source(self):
        respondents = {r["respondent"] for r in tables.read("survey/producer_survey")}
        self.assertEqual(len(respondents), 12)
        self.assertTrue({r["respondent"] for r in tables.read("survey/survey_rotations")} <= respondents)
        self.assertTrue({r["respondent"] for r in tables.read("survey/survey_unfavorable_seasons")} <= respondents)
        self.assertIn("producer_survey", tables.sources())

    def test_no_person_or_place_smaller_than_a_department_is_stored(self):
        self.assertTrue({r["department"] for r in tables.read("survey/producer_survey")} <= {"Soriano", "Río Negro", "Paysandú"})
        self.assertNotIn("locality", tables.read("survey/producer_survey")[0])

    def test_rotation_tokens_keep_the_written_order_per_respondent(self):
        self.assertEqual([c for _, c, _ in tables.survey_rotations()[3]], ["wheat", "soybean", "maize", "rapeseed"])
        self.assertEqual({g for g, _, _ in tables.survey_rotations()[9]}, {1, 2, 3, 4, 5})

    def test_two_seasons_stand_out_in_the_survey(self):
        self.assertEqual(tables.survey_seasons(), {"2025/26": 4, "2022/23": 4, "2024/25": 1})  # a single written year is not used


class SurveyValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = survey.run()

    def test_the_window_is_the_last_five_seasons(self):
        self.assertEqual(self.doc["window"], ["2021/22", "2022/23", "2023/24", "2024/25", "2025/26"])
        self.assertEqual(self.doc["respondents"], 12)
        self.assertEqual(self.doc["answered"], 8)

    def test_the_most_stressed_seasons_are_compared_with_the_most_named(self):
        for crop, entry in self.doc["crops"].items():
            self.assertEqual(len(entry["highest_stress"]), 2, crop)
            self.assertEqual(entry["agree"], set(entry["highest_stress"]) == set(entry["most_named"]), crop)

    def test_the_comparison_does_not_depend_on_the_reading(self):
        self.assertEqual(survey.run(), self.doc)


class SmapValidator(unittest.TestCase):
    """Synthetic NASA-shaped files: L4 is the model plus a fixed wobble, L3 a noisy copy of L4."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.ctx = context.build_context()
        fixtures.write_synthetic_smap(cls.dir.name, cls.ctx)
        cls.root = Path(cls.dir.name)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_loaders_keep_only_complete_days_and_recommended_quality(self):
        l4, l3 = smap.load_l4(self.root / "l4.csv"), smap.load_l3(self.root / "l3.csv")
        self.assertTrue(all(0 < v < 1 for v in l4.values()) and l3)
        self.assertTrue(all(d.toordinal() % 3 == 0 for d in l3))

    def test_the_model_tracks_data_it_was_built_from_better_than_a_rain_index(self):
        doc = smap.run(self.root / "l3.csv", self.root / "l4.csv", self.ctx)
        scores = doc["periods"]["validation"]["scores"]
        self.assertGreater(scores["model"]["spearman"], scores["rain_index"]["spearman"])
        self.assertGreater(scores["model"]["spearman"], 0.9)
        self.assertEqual(set(scores), {"model", "smap_l4", "rain_index"})

    @unittest.skipUnless(HAVE_MPL, "matplotlib is not installed")
    def test_validate_draws_every_figure_in_both_languages_with_the_smap_files(self):
        with tempfile.TemporaryDirectory() as out:
            args = ["validate", "--out", out, "--smap-l3", str(self.root / "l3.csv"), "--smap-l4", str(self.root / "l4.csv")]
            self.assertEqual(cli.main(args), 0)
            names = {p.name for p in Path(out).glob("*.png")}
            expected = {f"validation_{kind}.{lang}.png" for kind in ("survey", "smap") for lang in ("en", "es")}
            self.assertEqual(names, expected)

    def test_the_antecedent_index_decays_between_rains(self):
        weather = {date(2000, 1, 1) + timedelta(days=i): {"PRECTOTCORR": 10.0 if i == 0 else 0.0} for i in range(3)}
        index = smap.antecedent_index(weather, date(2000, 1, 3))
        self.assertAlmostEqual(index[date(2000, 1, 3)], 10 * smap.API_DECAY ** 2)


if __name__ == "__main__":
    unittest.main()
