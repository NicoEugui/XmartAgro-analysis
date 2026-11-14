"""Datasets grouped by site and by origin: the registry, the manifest and running either site."""
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
SORIANO_POWER_SHA256 = "9c85022f18c4905b7d88d1ad3146dd7239e7771b002942c2373781de3c421464"  # the file NASA delivered


def in_site(site, code):
    """Run code in a fresh process on another site (the site is chosen when the engine is imported)."""
    env = {**os.environ, "XMART_SITE": site, "PYTHONPATH": SRC}
    done = subprocess.run([sys.executable, "-W", "ignore", "-c", code], env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


class Registry(unittest.TestCase):
    def test_exactly_one_site_is_active_and_both_are_complete(self):
        self.assertEqual(sum(r["active"] == "1" for r in tables.sites().values()), 1)
        self.assertEqual(set(tables.sites()), {"la_estanzuela", "soriano"})
        self.assertEqual(tables.check_sites(), [])

    def test_the_default_site_is_the_inia_point_and_the_environment_overrides_it(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XMART_SITE", None)
            self.assertEqual(tables.active_site(), "la_estanzuela")
        with mock.patch.dict(os.environ, {"XMART_SITE": "soriano"}):
            self.assertEqual(tables.active_site(), "soriano")

    def test_an_unknown_site_is_a_structured_error(self):
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

    def test_the_station_belongs_to_the_inia_site_only(self):
        stations = [r["path"] for r in tables.manifest() if r["kind"] == "station"]
        self.assertEqual(stations, ["sites/la_estanzuela/station_daily.csv"])
        self.assertFalse((tables.site_dir("soriano") / "station_daily.csv").exists())

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


class EitherSite(unittest.TestCase):
    def test_the_soriano_site_runs_with_its_own_calibration_and_is_fitted(self):
        out = json.loads(in_site("soriano", """
import json
from xmart_analysis.engine import tables, water_model as wm
w = wm.load_power()
print(json.dumps({"lat": tables.constant("latitude"), "days": len(w), "seasons": len(tables.season_years()),
                  "current": tables.calibration_is_current(), "station": tables.site_file("station_daily.csv").exists()}))"""))
        self.assertEqual((out["lat"], out["days"], out["seasons"], out["current"], out["station"]),
                         (-33.3577778, 14610, 39, True, False))

    def test_the_inia_site_borrows_the_soriano_soil_and_says_it_is_pending(self):
        out = json.loads(in_site("la_estanzuela", """
import json
from xmart_analysis.engine import tables
print(json.dumps({"lat": tables.constant("latitude"), "current": tables.calibration_is_current(),
                  "from": tables.calibration_path().parent.name, "seasons": len(tables.season_years())}))"""))
        self.assertEqual((out["lat"], out["current"], out["from"], out["seasons"]), (-34.34, False, "soriano", 40))

    def test_the_whole_analysis_runs_on_the_soriano_site_too(self):
        with tempfile.TemporaryDirectory() as folder:
            code = f"import sys; from xmart_analysis import cli; sys.exit(cli.main(['run', '--out', {folder!r}, '--no-figures']))"
            in_site("soriano", code)
            self.assertTrue(any(Path(folder).glob("*.results.json")))


if __name__ == "__main__":
    unittest.main()
