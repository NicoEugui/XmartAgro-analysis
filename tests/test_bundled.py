"""The NASA files shipped in the repository: they are at the site's point, they reproduce the numbers the documents quote, and no account data came with them."""

import tempfile
import unittest

from xmart_analysis import cli
from xmart_analysis.engine import context as engine_context
from xmart_analysis.engine import tables
from xmart_analysis.validation import files, imerg, ndvi, smap

BUNDLED = ("power_daily.csv", "imerg_daily.csv", "smap_l4.csv", "smap_l3.csv", "modis_ndvi.csv")


class BundledNasaFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = engine_context.build_context()

    def path(self, name):
        return tables.site_file(name)

    def test_every_nasa_file_of_the_site_is_listed_in_the_manifest(self):
        listed = {r["path"].rsplit("/", 1)[1] for r in tables.manifest() if r["group"] == f"site:{tables.active_site()}"}
        self.assertLessEqual(set(BUNDLED), listed)

    def test_the_exports_are_at_the_sites_point(self):
        for name in ("smap_l4.csv", "smap_l3.csv", "modis_ndvi.csv"):
            files.check_point(self.path(name))

    def test_no_account_data_travels_with_the_files(self):
        for name in BUNDLED:
            self.assertNotIn("@", self.path(name).read_text(encoding="utf-8"), name)

    def test_smap_reproduces_the_quoted_correlations(self):
        scores = smap.run(self.path("smap_l3.csv"), self.path("smap_l4.csv"), self.context)["periods"]["validation"]["scores"]
        self.assertEqual((scores["model"]["spearman"], scores["model"]["anomaly_r"]), (0.781, 0.63))

    def test_modis_and_imerg_reproduce_the_quoted_numbers(self):
        correlations = ndvi.run(self.path("modis_ndvi.csv"), self.context)["correlations"]
        self.assertEqual((correlations["soybean_1st"]["spearman_ndvi_vs_minus_stress"], correlations["maize"]["spearman_ndvi_vs_minus_stress"]), (0.253, 0.291))
        rain = imerg.run(self.path("imerg_daily.csv"), self.context)["rain"]
        self.assertEqual((rain["daily_r"], rain["monthly_r"]), (0.764, 0.955))

    def test_the_flags_without_a_path_use_the_bundled_files(self):
        with tempfile.TemporaryDirectory() as out:
            code = cli.main(["validate", "--smap-l3", "--smap-l4", "--modis-ndvi", "--imerg", "--out", out, "--no-figures"])
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
