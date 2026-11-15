"""Data grouped by site and by origin: the registry, the manifest and running the site."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from xmart_analysis import datasets
from xmart_analysis.engine import tables
from xmart_analysis.engine.errors import EngineError

SRC = str(Path(__file__).resolve().parents[1] / "src")
SORIANO_POWER_SHA256 = "a855d2829db9392e5467ad1db59e652c72815809fc13b17908d9e9aea16556fb"  # the NASA download of 14 Nov 2026 (its last day had no values and was trimmed)


def in_site(site, code):
    """Run code in a fresh process (the site is chosen when the engine is imported)."""
    env = {**os.environ, "XMART_SITE": site, "PYTHONPATH": SRC}
    done = subprocess.run([sys.executable, "-W", "ignore", "-c", code], env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


class Registry(unittest.TestCase):
    def test_the_only_site_is_the_soriano_field_and_it_is_complete(self):
        self.assertEqual(set(tables.sites()), {"soriano"})
        self.assertEqual(tables.sites()["soriano"]["active"], "1")
        self.assertEqual(tables.check_sites(), [])

    def test_the_environment_can_name_the_site_and_an_unknown_one_is_a_structured_error(self):
        with mock.patch.dict(os.environ, {"XMART_SITE": "soriano"}):
            self.assertEqual(tables.active_site(), "soriano")
        with mock.patch.dict(os.environ, {"XMART_SITE": "nowhere"}):
            with self.assertRaises(EngineError) as ctx:
                tables.active_site()
        self.assertEqual(ctx.exception.code, "unknown_site")


class Manifest(unittest.TestCase):
    def test_every_dataset_matches_its_manifest_entry(self):
        self.assertEqual(tables.check_manifest(), [])

    def test_each_dataset_lives_in_the_folder_of_its_group(self):
        for row in tables.manifest():
            folder = "survey/" if row["group"] == "survey" else f"sites/{row['group'].split(':')[1]}/"
            self.assertTrue(row["path"].startswith(folder), row["path"])

    def test_the_only_external_data_is_nasa_and_the_teams_survey(self):
        real = [r for r in tables.manifest() if r["kind"] != tables.SIMULATED]
        self.assertEqual({r["source_ref"] for r in real}, {"nasa_power", "gpm_imerg", "smap_l4", "smap_l3", "modis_ndvi", "producer_survey"})
        self.assertEqual({r["kind"] for r in real}, {"climate", "fit", "survey", "soil_moisture", "vegetation"})
        self.assertEqual({r["source_ref"] for r in tables.manifest() if r["kind"] == tables.SIMULATED}, {"simulated_sensor"})

    def test_the_soriano_climate_is_exactly_the_file_nasa_delivered(self):
        digest = hashlib.sha256((tables.site_dir("soriano") / "power_daily.csv").read_bytes()).hexdigest()
        self.assertEqual(digest, SORIANO_POWER_SHA256)

    def test_a_changed_file_is_reported_as_not_matching_the_manifest(self):
        row = dict(tables.manifest()[0], sha256="0" * 64)
        with mock.patch.object(tables, "manifest", lambda: (row,)):
            self.assertTrue(any("sha256" in p for p in tables.check_manifest()))

    def test_a_dataset_missing_from_the_manifest_is_reported(self):
        with mock.patch.object(tables, "manifest", lambda: tuple(tables.read("datasets"))[1:]):
            self.assertTrue(any("is not listed" in p for p in tables.check_manifest()))

    def test_refreshing_the_manifest_changes_nothing_when_the_files_did_not_change(self):
        path = tables.DATA_DIR / "datasets.csv"
        before = path.read_bytes()
        datasets.refresh_manifest()
        self.assertEqual(path.read_bytes(), before)


class TheSite(unittest.TestCase):
    def test_the_site_runs_with_its_own_fitted_calibration(self):
        out = json.loads(in_site("soriano", """
import json
from xmart_analysis.engine import tables, water_model as wm
w = wm.load_power()
print(json.dumps({"lat": tables.constant("latitude"), "days": len(w), "seasons": len(tables.season_years()),
                  "current": tables.calibration_is_current()}))"""))
        self.assertEqual((out["lat"], out["days"], out["seasons"], out["current"]), (-33.3577778, 14746, 39, True))

    def test_the_whole_analysis_runs_on_it(self):
        with tempfile.TemporaryDirectory() as folder:
            code = f"import sys; from xmart_analysis import cli; sys.exit(cli.main(['run', '--out', {folder!r}, '--no-figures']))"
            in_site("soriano", code)
            self.assertTrue(any(Path(folder).glob("*.results.json")))


if __name__ == "__main__":
    unittest.main()
