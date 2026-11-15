"""The calendar of the front document: the field on any date of the last year, for every crop that can be sown."""

import importlib.util
import unittest
from datetime import date, timedelta

import learned
from xmart_analysis import cli
from xmart_analysis.engine import calendar_grid, crops_uy as cu
from xmart_analysis.engine import platform_session as ps
from xmart_analysis.frontend import payload

HAVE_LEARN = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "sklearn"))
NOW = "2026-11-14T10:30:00+00:00"


class Dates(unittest.TestCase):
    def test_the_next_sowing_is_on_or_after_the_date_and_wraps_to_next_year(self):
        month, day = cu.CROPS["wheat"]["sowing"]
        self.assertEqual(calendar_grid.next_sowing("wheat", date(2026, month, day)), ((month, day), 0))
        (m, d), days = calendar_grid.next_sowing("wheat", date(2026, month, day) + timedelta(days=1))
        self.assertEqual((m, d), (month, day))
        self.assertEqual(days, 364)  # the sowing of the following year

    def test_the_calendar_days_end_on_the_last_day_and_step_back_by_the_constant(self):
        states = {date(2026, 1, 1) + timedelta(days=i): 0.3 for i in range(30)}
        days = calendar_grid.calendar_days(states, 7)
        self.assertEqual(days, [date(2026, 1, 2), date(2026, 1, 9), date(2026, 1, 16), date(2026, 1, 23), date(2026, 1, 30)])


class Plain(unittest.TestCase):
    """Without models: the sensor series of the demo and the fixed cuts."""

    @classmethod
    def setUpClass(cls):
        cls.doc = cli.frontend_document(None, NOW)
        cls.calendar = cls.doc["calendar"]

    def test_the_calendar_ends_on_the_day_the_summary_is_for(self):
        self.assertEqual(self.calendar["to"], self.doc["as_of"])
        self.assertEqual(self.calendar["dates"][-1]["date"], self.calendar["to"])
        self.assertEqual(self.calendar["from"], self.calendar["dates"][0]["date"])

    def test_the_last_date_has_the_water_the_main_screen_shows(self):
        water, shown = self.calendar["dates"][-1]["water"], self.doc["summary"]["water"]
        self.assertAlmostEqual(water["mm"], shown["mm"], delta=0.5)
        self.assertEqual(water["capacity_mm"], shown["capacity_mm"])

    def test_dates_are_a_week_apart_oldest_first_and_cover_a_year(self):
        days = [date.fromisoformat(e["date"]) for e in self.calendar["dates"]]
        self.assertEqual(days, sorted(days))
        self.assertEqual({(b - a).days for a, b in zip(days, days[1:])}, {self.calendar["step_days"]})
        self.assertGreaterEqual((days[-1] - days[0]).days, 350)

    def test_every_date_has_every_crop_that_can_be_sown_with_ten_drops(self):
        for entry in self.calendar["dates"]:
            self.assertEqual([o["crop"] for o in entry["options"]], ps.CROP_CHOICES)
            for option in entry["options"]:
                self.assertEqual(sum(option["drops"].values()), 10)
                self.assertEqual(option["risk_basis"]["source"], "fixed_cuts")
                self.assertEqual(option["offered"], option["days_to_sowing"] <= self.calendar["offer_days"])

    def test_what_is_offered_follows_the_season(self):
        by_date = {e["date"]: {o["crop"] for o in e["options"] if o["offered"]} for e in self.calendar["dates"]}
        spring = by_date[min(by_date, key=lambda d: abs((date.fromisoformat(d) - date(2026, 9, 4)).days))]
        autumn = by_date[min(by_date, key=lambda d: abs((date.fromisoformat(d) - date(2026, 5, 1)).days))]
        self.assertIn("soybean_1st", spring)
        self.assertNotIn("soybean_1st", autumn)
        self.assertTrue({"wheat", "barley"} <= autumn)

    def test_a_cell_is_what_the_engine_gives_for_that_date_and_crop(self):
        entry = self.calendar["dates"][len(self.calendar["dates"]) // 2]
        day = date.fromisoformat(entry["date"])
        from xmart_analysis.engine import context
        ctx = context.build_context()
        kw = {"params": ctx["params"], "weather": ctx["weather"], "et0": ctx["et0"]}
        cell = next(o for o in entry["options"] if o["crop"] == "maize")
        sowing, days = calendar_grid.next_sowing("maize", day)
        # the state of that day is the one the calendar holds: its mm is the same estimate the engine turns into drops
        card = ps.crop_card("maize", sowing, entry["water"]["volumetric_moisture"], (day.month, day.day), False, kw, {"source": "x", "is_simulated": True})
        self.assertEqual((cell["sowing"], cell["days_to_sowing"]), (card["sowing"], days))
        self.assertEqual(cell["drops"], {"ok": card["split_in_10_parts"]["low_deficit"], "tight": card["split_in_10_parts"]["moderate_deficit"],
                                        "out": card["split_in_10_parts"]["high_deficit"]})

    def test_the_far_warning_has_its_text_and_every_code_used_is_explained(self):
        codes = {w["code"] for w in self.calendar["warnings"]}
        used = {c for e in self.calendar["dates"] for o in e["options"] for c in o["warnings"]}
        self.assertTrue(used <= codes)
        for w in self.calendar["warnings"]:
            self.assertEqual(set(w["text"]), {"key", "en", "es"})

    def test_the_water_changes_across_the_year(self):
        waters = {e["water"]["mm"] for e in self.calendar["dates"]}
        self.assertGreater(len(waters), 30)


@unittest.skipUnless(HAVE_LEARN, "numpy, scipy and scikit-learn are not installed")
class WithModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = cli.frontend_document(None, NOW, learned.folder())
        cls.calendar = cls.doc["calendar"]

    def test_the_last_date_has_the_water_model_b_sets_for_the_main_screen(self):
        self.assertAlmostEqual(self.calendar["dates"][-1]["water"]["mm"], self.doc["summary"]["water"]["mm"], delta=0.5)

    def test_cells_carry_model_a_drops_with_the_fixed_cuts_beside_them(self):
        basis = [o["risk_basis"] for e in self.calendar["dates"] for o in e["options"]]
        self.assertEqual({b["source"] for b in basis}, {"model_a"})
        self.assertTrue(all(b["model_version"] == 1 for b in basis))
        different = [o for e in self.calendar["dates"] for o in e["options"] if o["drops"] != o["risk_basis"]["fixed_cuts_drops"]]
        self.assertTrue(different)  # A reads the seasons differently from the fixed cuts somewhere

    def test_the_water_is_not_the_one_the_plain_sensor_series_gives(self):
        plain = cli.frontend_document(None, NOW)["calendar"]
        self.assertNotEqual([e["water"]["mm"] for e in plain["dates"]], [e["water"]["mm"] for e in self.calendar["dates"]])


class Cache(unittest.TestCase):
    def test_the_same_session_is_worked_out_once(self):
        cli.frontend_document(None, NOW)
        before = dict(payload._GRIDS)
        cli.frontend_document(None, NOW)
        self.assertEqual(set(before), set(payload._GRIDS))


if __name__ == "__main__":
    unittest.main()
