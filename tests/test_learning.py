"""The learning layer: a simulated, honest panel, three models judged on fields they never saw, and a registry that never publishes a worse one."""

import importlib.util
import json
import random
import tempfile
import unittest
from datetime import date
from pathlib import Path

from xmart_analysis import cli
from xmart_analysis.engine import sensor_series, tables

HAVE_LEARN = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "sklearn"))
NEEDS = unittest.skipUnless(HAVE_LEARN, "numpy, scipy and scikit-learn are not installed")
if HAVE_LEARN:
    from xmart_analysis.learning import examples, fields, models, ndvi, nodes, outcomes, pooling, producers, soil_plans, training, validation
    from xmart_analysis.learning.registry import Registry


@NEEDS
class Tables(unittest.TestCase):
    def test_two_real_fields_and_the_rest_simulated_with_a_planted_satellite_error(self):
        everything = fields.all_fields()
        self.assertEqual([f.field_id for f in everything if f.real], ["soriano", "la_estanzuela"])
        self.assertEqual({f.site_id for f in everything if f.real}, {"soriano", "la_estanzuela"})  # each real field has its own NASA site
        for f in everything:
            self.assertEqual(f.smap_offset is None, f.real, f.field_id)  # the real field is seen through the real satellite

    def test_the_real_field_has_the_soil_of_the_sensor_experiment(self):
        soriano = fields.get("soriano")
        self.assertEqual(soriano.capacity_factor, tables.constant("sensor_truth_capacity_factor"))
        self.assertEqual(soriano.theta_min_shift, tables.constant("sensor_truth_theta_min_shift"))

    def test_every_field_has_at_least_two_nodes_at_different_depths(self):
        for f in fields.all_fields():
            depths = {n.depth_cm for n in nodes.of_field(f.field_id)}
            self.assertGreaterEqual(len(depths), 2, f.field_id)
            self.assertIn(30, depths)  # the minimum depth of the sensor contract

    def test_every_field_has_its_own_nasa_climate_at_its_own_point_in_its_own_grid_cell(self):
        cells = {}
        for f in fields.all_fields():
            point = tables.constants_of(f.site_id)
            self.assertEqual((point["latitude"], point["longitude"]), (f.latitude, f.longitude), f.field_id)
            self.assertEqual(tables.sites()[f.site_id]["kind"], "field" if f.real else "climate")
            cells.setdefault((round(f.latitude / 0.5), round((f.longitude + 180) / 0.625)), []).append(f.field_id)
        self.assertEqual({c: n for c, n in cells.items() if len(n) > 1}, {})  # POWER's cell is 0.5 x 0.625 degrees: one field per cell

    def test_the_producers_are_the_twelve_respondents_and_their_variants_stay_in_the_published_ranges(self):
        everyone = producers.all_producers()
        self.assertEqual(sorted(p.respondent for p in everyone), list(range(1, 13)))
        for p in everyone:
            for crop, bounds in producers.crop_ranges().items():
                variant = producers.crop_variant(crop, p)
                self.assertTrue(bounds["kc_mid_min"] * 0.95 <= variant["kc"][1] <= bounds["kc_mid_max"] * 1.05, (p.producer_id, crop))
                self.assertTrue(0.1 <= variant["p"] <= 0.8)
        self.assertEqual(producers.crop_variant("maize"), dict(tables.crops()["maize"]))  # no producer, the table's crop

    def test_every_field_has_a_simulated_soil_plan_inside_the_ranges_the_contract_accepts(self):
        plans = {p.field_id: p for p in soil_plans.all_plans()}
        self.assertEqual(set(plans), {f.field_id for f in fields.all_fields()})
        for name, plan in plans.items():
            self.assertEqual(plan.status, "simulated", name)  # the analysis numbers are simulated
            self.assertEqual(plan.coneat, fields.get(name).soil_unit.code, name)  # the soil unit is not: it is the field's CONEAT group
            for value, key in ((plan.organic_matter_pct, "organic_matter_pct"), (plan.phosphorus_bray_ppm, "phosphorus_ppm"),
                               (plan.ph, "ph"), (plan.erosion_t_ha_yr, "erosion_t_ha_yr")):
                self.assertTrue(tables.constant(f"{key}_min") <= value <= tables.constant(f"{key}_max"), (name, key, value))

    def test_the_soil_plans_follow_the_soil_and_the_slope_of_their_field(self):
        mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
        by_clay = {c: [soil_plans.of_field(f.field_id) for f in fields.all_fields() if f.clay == c] for c in (0, 1, 2)}
        self.assertLess(mean([p.organic_matter_pct for p in by_clay[0]]), mean([p.organic_matter_pct for p in by_clay[2]]))
        steep = [soil_plans.of_field(f.field_id).erosion_t_ha_yr for f in fields.all_fields() if f.slope_pct >= 4]
        flat = [soil_plans.of_field(f.field_id).erosion_t_ha_yr for f in fields.all_fields() if f.slope_pct <= 1]
        self.assertGreater(mean(steep), mean(flat))

    def test_crop_ranges_say_where_each_value_comes_from(self):
        for crop, row in producers.crop_ranges().items():
            self.assertIn(row["ky_status"], ("source", "assumption"), crop)
            self.assertIn("fao56", row["source_ref"])

    def test_a_producer_who_wrote_no_rotation_gets_the_crops_every_respondent_wrote(self):
        self.assertNotIn(5, tables.survey_rotations())
        self.assertEqual(producers.crop_sequence(5), [c for r in sorted(tables.survey_rotations()) for c in producers.crop_sequence(r)])


@NEEDS
class Panel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = examples.Panel()
        cls.records = cls.panel.season_records()
        cls.sensor = cls.panel.sensor_rows()

    def test_twelve_producers_five_seasons_each_make_sixty_seasons(self):
        mine = [r for r in self.records if r["producer_id"]]
        self.assertEqual(len(mine), 60)
        self.assertEqual({p.producer_id: sum(r["producer_id"] == p.producer_id for r in mine) for p in producers.all_producers()},
                         {p.producer_id: 5 for p in producers.all_producers()})

    def test_every_row_says_it_is_simulated_and_where_from(self):
        for r in [*self.records, *self.sensor]:
            self.assertTrue(r["simulated"])
            self.assertEqual(r["source"], outcomes.SOURCE)

    def test_the_real_satellite_is_marked_as_real_and_the_others_as_simulated(self):
        flags = {r["field_id"]: r["satellite_simulated"] for r in self.sensor}
        self.assertEqual({k for k, v in flags.items() if not v}, {"soriano", "la_estanzuela"})

    def test_each_field_rains_on_its_own_days_and_the_real_ones_are_their_sites_as_is(self):
        def daily_rain(field_id):
            weather = self.panel.contexts[field_id]["weather"]
            return [weather[d]["PRECTOTCORR"] for d in sorted(weather)]

        def correlation(a, b):
            ma, mb = sum(a) / len(a), sum(b) / len(b)
            cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
            return cov / (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
        soriano, salto, florida = daily_rain("soriano"), daily_rain("sim_salto"), daily_rain("sim_florida")
        self.assertLess(correlation(soriano, salto), 0.95)  # not the same rainy days
        self.assertLess(correlation(salto, florida), 0.95)
        self.assertGreater(correlation(soriano, salto), 0.3)  # but the same climate
        for real in ("soriano", "la_estanzuela"):
            self.assertIs(self.panel.contexts[real], self.panel.sites[real])

    def test_a_simulated_field_has_its_own_dry_years(self):
        def annual(field_id):
            totals = {}
            for d, w in self.panel.contexts[field_id]["weather"].items():
                totals[d.year] = totals.get(d.year, 0.0) + w["PRECTOTCORR"]
            return totals
        rank = lambda t: sorted((y for y in t if 1987 <= y <= 2025), key=t.get)[:5]  # noqa: E731
        self.assertNotEqual(rank(annual("sim_durazno")), rank(annual("soriano")))
        self.assertNotEqual(rank(annual("sim_salto")), rank(annual("sim_florida")))

    def test_la_estanzuela_runs_on_its_own_climate_and_its_own_calibration(self):
        mine, soriano = self.panel.contexts["la_estanzuela"], self.panel.contexts["soriano"]
        self.assertNotEqual(mine["params"], soriano["params"])
        day = max(mine["weather"])
        self.assertNotEqual(mine["weather"][day], soriano["weather"][day])

    def test_the_panel_is_the_same_every_time(self):
        again = examples.Panel(self.panel.sites).season_records()
        self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(self.records, sort_keys=True))

    def test_ratings_cover_the_whole_scale_and_fallow_has_none(self):
        self.assertEqual({r["rating"] for r in self.records if r["rating"]}, {1, 2, 3, 4, 5})
        self.assertTrue(all(r["rating"] is None and r["model_stress"] is None for r in self.records if r["crop"] == producers.FALLOW))

    def test_the_drought_of_2022_stresses_maize_more_than_a_normal_year(self):
        def mean_stress(season):
            rows = [r["model_stress"] for r in self.records if not r["producer_id"] and r["season"] == season and r["crop"] == "maize"]
            return sum(rows) / len(rows)
        self.assertGreater(mean_stress("2022/23"), mean_stress("2020/21"))

    def test_more_stress_means_a_lower_yield_on_average(self):
        rated = examples.rated(self.records)
        low = [r["relative_yield"] for r in rated if r["truth_stress"] < 0.1]
        high = [r["relative_yield"] for r in rated if r["truth_stress"] > 0.4]
        self.assertGreater(sum(low) / len(low), sum(high) / len(high))

    def test_a_node_reading_is_calibrated_by_a_reference_measurement(self):
        field = fields.get("sim_paysandu")
        context = self.panel.contexts[field.field_id]
        window = sensor_series.span(context["weather"])
        node = nodes.of_field(field.field_id)[0]
        raw = nodes.readings(node, field, context, window)
        self.assertAlmostEqual(nodes.reference_offset(node), node.bias, delta=0.03)
        day = sorted(raw)[200]
        self.assertAlmostEqual(nodes.calibrated(node, raw)[day], raw[day] - nodes.reference_offset(node), places=3)


@NEEDS
class Ndvi(unittest.TestCase):
    def test_a_summer_crop_peaks_later_than_a_winter_crop_and_fallow_never_greens(self):
        rng, spec = random.Random(1), tables.crops()
        winter = ndvi.summary(ndvi.curve(2021, "wheat", date(2021, 6, 15), spec["wheat"], 0.0, 0.82, rng))
        summer = ndvi.summary(ndvi.curve(2021, "soybean_1st", date(2021, 11, 15), spec["soybean_1st"], 0.0, 0.8, rng))
        bare = ndvi.summary(ndvi.curve(2021, None, None, None, 0.0, 0.0, rng))
        self.assertGreater(summer["peak_offset"], winter["peak_offset"])
        self.assertGreater(winter["duration_days"], bare["duration_days"])
        self.assertGreater(winter["peak_value"], bare["peak_value"] + 0.3)

    def test_stress_lowers_the_peak(self):
        spec = tables.crops()["maize"]
        peaks = [ndvi.summary(ndvi.curve(2021, "maize", date(2021, 10, 1), spec, s, 0.88, random.Random(2)))["peak_value"] for s in (0.0, 0.8)]
        self.assertGreater(peaks[0], peaks[1])


@NEEDS
class Pooling(unittest.TestCase):
    def test_a_field_without_data_is_the_region_and_one_with_many_is_itself(self):
        self.assertEqual(pooling.shrink(0, 5.0, 1.0, 4), 1.0)
        self.assertAlmostEqual(pooling.shrink(4, 5.0, 1.0, 4), 3.0)  # n = k: both weigh the same
        self.assertAlmostEqual(pooling.shrink(10_000, 5.0, 1.0, 4), 5.0, places=2)


@NEEDS
class Models(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = training.datasets(examples.Panel())

    def test_b_corrects_the_satellite_better_with_every_step_of_information(self):
        check = validation.holdout(models.ModelB, self.data["B"])["metrics"]
        days = tables.constant("learn_min_days_b")
        self.assertLess(check["regional_rmse"]["mean"], check["satellite_rmse"]["mean"])
        self.assertLess(check[f"with_{days}_days_rmse"]["mean"], check["regional_rmse"]["mean"])

    def test_a_gives_a_worse_season_a_higher_chance_of_being_bad(self):
        model = models.ModelA().fit(self.data["A"])
        for crop in ("soybean_1st", "maize", "wheat"):
            bad = [model.predict_proba(crop, s)[0] for s in (0.0, 0.2, 0.4, 0.8)]
            self.assertEqual(bad, sorted(bad), crop)
            self.assertAlmostEqual(float(sum(model.predict_proba(crop, 0.3))), 1.0)

    def test_c_tells_the_crop_season_from_the_curve_of_a_field_it_never_saw(self):
        check = validation.holdout(models.ModelC, self.data["C"], rounds=3)["metrics"]
        self.assertGreater(check["season_group_accuracy"]["mean"], 0.9)
        self.assertGreater(check["accuracy"]["mean"], check["most_common_accuracy"]["mean"] + 0.3)

    def test_validation_never_trains_on_a_field_it_tests_on(self):
        seen = []

        class Spy(models.Learner):
            name, primary, baseline = "S", "x", "y"

            def fit(self, rows):
                self.train = {r["field_id"] for r in rows}
                return self

            def metrics(self, rows):
                seen.append((self.train, {r["field_id"] for r in rows}))
                return {"x": 0.0, "y": 0.0}
        validation.holdout(Spy, self.data["B"], rounds=5)
        self.assertEqual(len(seen), 5)
        for trained, tested in seen:
            self.assertEqual(trained & tested, set())
            self.assertEqual(len(tested), 2)  # a quarter of eight fields


@NEEDS
class RegistryRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = training.datasets(examples.Panel())["B"]

    def register(self, registry, rows, better=True):
        model = models.ModelB().fit(rows)
        check = {"metrics": {"regional_rmse": {"mean": 0.02}, "satellite_rmse": {"mean": 0.03 if better else 0.01}}}
        return registry.register(model, check, len(rows), 8, "2026-11-15", model.ready(rows), True)

    def test_a_better_model_is_published_and_retires_the_previous_one(self):
        with tempfile.TemporaryDirectory() as folder:
            registry = Registry(folder)
            first, second = self.register(registry, self.rows), self.register(registry, self.rows)
            self.assertEqual((first["version"], second["version"]), (1, 2))
            self.assertEqual([e["state"] for e in registry.entries()], ["retired", "published"])
            entry, model = registry.published("B")
            self.assertEqual(entry["version"], 2)
            self.assertTrue(hasattr(model, "regional"))

    def test_a_worse_model_stays_a_candidate_and_the_published_one_keeps_serving(self):
        with tempfile.TemporaryDirectory() as folder:
            registry = Registry(folder)
            self.register(registry, self.rows)
            worse = self.register(registry, self.rows, better=False)
            self.assertEqual(worse["state"], "candidate")
            self.assertIn("does not beat", worse["reason"])
            self.assertEqual(registry.published("B")[0]["version"], 1)

    def test_too_little_data_is_never_published(self):
        with tempfile.TemporaryDirectory() as folder:
            registry = Registry(folder)
            entry = self.register(registry, self.rows[:200])
            self.assertEqual(entry["state"], "candidate")
            self.assertIn("days of overlap", entry["reason"])
            self.assertIsNone(registry.published("B"))

    def test_an_empty_registry_has_nothing_published(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(Registry(folder).published("A"))


@NEEDS
class Command(unittest.TestCase):
    def test_learn_trains_registers_and_says_the_data_is_simulated(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(cli.main(["learn", "--out", folder, "--only", "B", "--now", "2026-11-15T00:00:00+00:00"]), 0)
            report = json.loads((Path(folder) / "learning.json").read_text(encoding="utf-8"))
            self.assertEqual(report["trained_on"], "2026-11-15")
            self.assertEqual(list(report["models"]), ["B"])
            self.assertTrue(report["models"]["B"]["simulated_data"])
            self.assertIn("simulated panel", report["reading"])
            self.assertTrue((Path(folder) / "registry.json").exists())


if __name__ == "__main__":
    unittest.main()
