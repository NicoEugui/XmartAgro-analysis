"""Rainfall accumulation tests: full January and leap-year February. Run: python3 test_rainfall.py"""
import unittest
from datetime import date, timedelta

from xmart_analysis.engine import water_model as wm
from xmart_analysis.engine.errors import EngineError


def weather_series(start, end, mm=1.0):
    day, out = start, {}
    while day <= end:
        out[day] = {"PRECTOTCORR": mm}
        day += timedelta(days=1)
    return out


class RainBetween(unittest.TestCase):
    def setUp(self):
        self.w = weather_series(date(2023, 1, 1), date(2024, 12, 31))

    def test_january_has_31_days(self):
        self.assertEqual(wm.rain_between(self.w, date(2023, 1, 1), date(2023, 2, 1)), 31)

    def test_january_february_non_leap(self):
        self.assertEqual(wm.rain_between(self.w, date(2023, 1, 1), date(2023, 3, 1)), 59)

    def test_january_february_leap_includes_the_29th(self):
        self.assertEqual(wm.rain_between(self.w, date(2024, 1, 1), date(2024, 3, 1)), 60)

    def test_the_29th_of_february_contributes_its_rain(self):
        self.w[date(2024, 2, 29)] = {"PRECTOTCORR": 40.0}
        self.assertEqual(wm.rain_between(self.w, date(2024, 1, 1), date(2024, 3, 1)), 99)

    def test_the_31st_of_january_contributes_its_rain(self):
        self.w[date(2023, 1, 31)] = {"PRECTOTCORR": 25.0}
        self.assertEqual(wm.rain_between(self.w, date(2023, 1, 1), date(2023, 3, 1)), 83)

    def test_fails_if_a_day_is_missing(self):
        del self.w[date(2023, 1, 15)]
        with self.assertRaises(EngineError) as ctx:
            wm.rain_between(self.w, date(2023, 1, 1), date(2023, 3, 1))
        self.assertEqual(ctx.exception.code, "missing_climate_day")
        self.assertEqual(ctx.exception.details["day"], "2023-01-15")

    def test_real_power_series_has_every_day(self):
        weather = wm.load_power()
        for k in range(1987, 2026):
            wm.rain_between(weather, date(k + 1, 1, 1), date(k + 1, 3, 1))


if __name__ == "__main__":
    unittest.main()
