"""Weather-station validation: the dataset is sound and the comparison measures what it says."""
import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from xmart_analysis.engine import context, tables
from xmart_analysis.engine import water_model as wm
from xmart_analysis.validation import station


class Dataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = station.load()

    def test_the_record_is_continuous_with_no_missing_day(self):
        days = sorted(self.data)
        self.assertEqual((days[-1] - days[0]).days + 1, len(days))

    def test_values_present_are_physically_possible(self):
        for d, v in self.data.items():
            self.assertTrue(0 <= v["rain_mm"] < 400, d)
            if v["tmin_c"] is not None and v["tmax_c"] is not None:
                self.assertTrue(v["tmin_c"] <= v["tmax_c"] and -10 < v["tmin_c"] and v["tmax_c"] < 50, d)

    def test_missing_values_are_rare_and_never_filled_in(self):
        for column in ("tmax_c", "tmin_c", "penman_et_mm"):
            missing = sum(v[column] is None for v in self.data.values())
            self.assertLess(missing / len(self.data), 0.005, column)
        self.assertEqual(sum(v["rain_mm"] is None for v in self.data.values()), 0)

    def test_it_covers_the_whole_nasa_record(self):
        weather = context.build_context()["weather"]
        self.assertTrue(set(weather) <= set(self.data))

    def test_it_is_listed_as_validation_data_of_the_inia_site(self):
        row = next(r for r in tables.manifest() if r["path"] == "sites/la_estanzuela/station_daily.csv")
        self.assertEqual((row["group"], row["role"], row["source_ref"]), ("site:la_estanzuela", "validation", "inia_la_estanzuela"))


class Import(unittest.TestCase):
    def test_import_keeps_the_model_columns_from_a_station_export(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "export.csv", Path(folder) / "out.csv"
            header = ["Fecha", *station.SOURCE_COLUMNS.values(), "Otra"]
            lines = ["Station name", ",".join(header), "1986-06-30,1,2,3,4,5,x", "1986-07-01,0.0,13.1,2.7,1.3,269.9,x", "notes at the end"]
            source.write_text("\n".join(lines), encoding="utf-8")
            self.assertEqual(station.import_station(source, target), 1)
            rows = list(csv.DictReader(open(target, encoding="utf-8")))
            self.assertEqual(rows[0], {"date": "1986-07-01", "rain_mm": "0.0", "tmax_c": "13.1", "tmin_c": "2.7",
                                       "penman_et_mm": "1.3", "solar_cal_cm2": "269.9"})


class Comparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = context.build_context()

    def test_a_station_equal_to_the_nasa_series_agrees_perfectly(self):
        weather = self.ctx["weather"]
        raw_et0 = wm.precompute_et0(weather, scale=1.0)
        copy = {d: {"rain_mm": w["PRECTOTCORR"], "tmax_c": w["T2M_MAX"], "tmin_c": w["T2M_MIN"],
                    "penman_et_mm": raw_et0[d], "solar_cal_cm2": 0.0} for d, w in weather.items()}
        doc = station.run(self.ctx, copy)
        self.assertEqual((doc["rain"]["monthly_r"], doc["rain"]["daily_r"]), (1.0, 1.0))
        self.assertEqual(doc["evapotranspiration"]["model_over_station"], 1.0)
        self.assertEqual(doc["temperature"]["tmax_c"]["power_minus_station_c"], 0.0)

    def test_the_real_station_agrees_on_monthly_rain_and_on_the_driest_season(self):
        doc = station.run(self.ctx)
        self.assertGreater(doc["rain"]["monthly_r"], 0.75)
        self.assertGreater(doc["rain"]["season_dec_mar_r"], 0.70)
        self.assertEqual(doc["driest_seasons"]["station"][0], doc["driest_seasons"]["power"][0])  # 2022/23 in both

    def test_the_window_of_the_survey_has_the_two_driest_of_its_five_at_the_station(self):
        seasons = {r["season"]: r["station_mm"] for r in station.run(self.ctx)["seasons_dec_mar"]}
        window = ["2021/22", "2022/23", "2023/24", "2024/25", "2025/26"]
        self.assertEqual(sorted(window, key=seasons.get)[:2], ["2022/23", "2025/26"])

    def test_season_rain_sums_the_121_days_from_the_first_of_december(self):
        series = {date(2000, 12, 1) + timedelta(days=i): 1.0 for i in range(200)}
        self.assertEqual(station.season_rain(series, 2000), 121.0)


if __name__ == "__main__":
    unittest.main()

