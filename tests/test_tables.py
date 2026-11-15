"""Data tables: every value has a status, only NASA sources are cited, and the engine reads the tables."""
import unittest

from xmart_analysis import provenance
from xmart_analysis.engine import crops_uy as cu
from xmart_analysis.engine import sowing_scenarios as sw
from xmart_analysis.engine import tables
from xmart_analysis.engine import water_scenarios as ws


class Provenance(unittest.TestCase):
    def test_every_value_has_a_known_status_and_a_source_when_it_needs_one(self):
        self.assertEqual(tables.validate(), [])

    def test_the_check_command_succeeds_on_the_shipped_tables(self):
        self.assertEqual(provenance.main(["--check"]), 0)

    def test_only_nasa_and_the_teams_own_survey_are_cited(self):
        self.assertEqual(set(tables.sources()), {"nasa_power", "smap_l4", "smap_l3", "modis_ndvi", "gpm_imerg", "producer_survey", "simulated_sensor"})
        self.assertEqual({r["publisher"] for r in tables.sources().values()}, {"NASA", "XmartAgro team"})

    def test_crop_parameters_wait_for_a_dataset_and_say_so(self):
        for crop, spec in cu.CROPS.items():
            self.assertEqual(set(spec["status"]), set(tables.GROUPS), crop)
            self.assertEqual(set(spec["status"].values()), {"pending"}, crop)

    def test_climate_and_the_model_point_are_data(self):
        rows = tables.provenance()
        self.assertEqual(next(r for r in rows if r["item"] == "latitude")["status"], "data")
        self.assertEqual(next(r for r in rows if r["item"] == "longitude")["status"], "data")

    def test_calibration_counts_as_fitted_only_when_it_matches_the_point_and_the_demand(self):
        expected = "fitted" if tables.calibration_is_current() else "pending"
        self.assertEqual({r["status"] for r in tables.provenance() if r["table"] == "calibration"}, {expected})

    def test_a_calibration_from_another_point_is_reported_pending(self):
        original = tables.calibration
        for change in ({"point": {"latitude": 0.0, "longitude": 0.0}},):
            tables.calibration = lambda change=change: {**original(), **change}
            try:
                self.assertFalse(tables.calibration_is_current())
                rows = [r for r in tables.provenance() if r["table"] == "calibration"]
                self.assertEqual({r["status"] for r in rows}, {"pending"})
                self.assertEqual(tables.validate(), [])
            finally:
                tables.calibration = original

    def test_a_source_status_without_a_source_is_reported(self):
        original = tables.provenance
        tables.provenance = lambda: [{"table": "t", "item": "x", "status": "source", "source_ref": "", "note": ""}]
        try:
            self.assertTrue(tables.validate())
        finally:
            tables.provenance = original

    def test_a_missing_constant_is_a_structured_error(self):
        with self.assertRaises(Exception) as ctx:
            tables.constant("not_a_constant")
        self.assertEqual(ctx.exception.code, "unknown_constant")


class SingleSourceOfTruth(unittest.TestCase):
    def test_season_years_come_from_one_place(self):
        self.assertEqual(ws.SEASON_YEARS, tables.season_years())

    def test_step_is_not_defined_twice(self):
        self.assertEqual(sw.STEP, ws.STEP)

    def test_every_perennial_has_no_sowing_date_and_every_annual_has_one(self):
        for crop, spec in cu.CROPS.items():
            self.assertEqual("sowing" in spec, not spec.get("perennial", False), crop)

    def test_unsupported_crops_are_not_simulated(self):
        self.assertEqual(set(cu.UNSUPPORTED_CROPS) & set(cu.CROPS), set())


if __name__ == "__main__":
    unittest.main()
