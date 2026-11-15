"""The soil-map module: a port any country's soil system fits, CONEAT as its first adapter, and what the panel takes from a unit."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from xmart_analysis import cli
from xmart_analysis.engine import tables
from xmart_analysis.soils import SYSTEMS, NullSoilMap, SoilUnit, derive, groups, units

HAVE_CONEAT = all(importlib.util.find_spec(m) for m in ("shapefile", "pyproj"))
HAVE_LEARN = all(importlib.util.find_spec(m) for m in ("numpy", "scipy", "sklearn"))

DESCRIPTION = """
1.10a
El relieve es de sierras. Los suelos dominantes son Litosoles Subéutricos Melánicos. Como asociados, Brunosoles
Éutricos Típicos. Indice de Productividad 70.

10.6a
Este grupo se localiza como una faja. Los suelos predominantes corresponden a Brunosoles Subéutricos y
Vertisoles Háplicos. Asociados aparecen Planosoles. Indice de Productividad 206. En otra región Indice de Productividad 131.

07.1
Suelos dominantes: Inceptisoles Ócricos. Indice de Productividad 31.

7.1
duplicate of the group above. Indice de Productividad 99.
"""


class Groups(unittest.TestCase):
    def test_the_description_gives_each_group_its_index_and_its_dominant_orders(self):
        rows = {r["code"]: r for r in groups.parse(DESCRIPTION)}
        self.assertEqual(set(rows), {"1.10a", "10.6a", "7.1"})
        self.assertEqual((rows["1.10a"]["productivity_index"], rows["1.10a"]["dominant_orders"]), (70.0, "Litosol"))
        self.assertEqual(rows["10.6a"]["productivity_index"], 168.5)  # two regions: the mean is kept, the values too
        self.assertEqual(rows["10.6a"]["index_values"], "206;131")
        self.assertEqual(rows["10.6a"]["dominant_orders"], "Brunosol;Vertisol")  # only what comes before the associated soils
        self.assertEqual(rows["7.1"]["productivity_index"], 31.0)  # the first block of a duplicated group wins

    def test_a_code_is_written_the_way_the_description_writes_it(self):
        self.assertEqual([groups.normalize(c) for c in ("07.1", "8.02a", "12.11", "3.10", "03.10")], ["7.1", "8.02a", "12.11", "3.10", "3.10"])

    def test_the_committed_table_has_the_groups_the_fields_fall_in(self):
        table = {r["code"]: r for r in tables.read("soils/coneat_groups")}
        self.assertGreater(len(table), 100)
        self.assertEqual({c for c in table if c != groups.normalize(c)}, set())
        self.assertEqual(float(table["11.4"]["productivity_index"]), 214.0)
        self.assertEqual(table["12.11"]["dominant_orders"], "Vertisol;Brunosol")
        found = {r["code"] for r in tables.read("learning/soil_units")}
        self.assertLessEqual(found, set(table))


class Derivations(unittest.TestCase):
    def unit(self, orders, index=100.0):
        return SoilUnit("coneat", "x", index, tuple(orders))

    def test_texture_is_the_heaviest_of_the_first_two_orders(self):
        self.assertEqual(derive.texture_class(self.unit(["Litosol"])), 0)
        self.assertEqual(derive.texture_class(self.unit(["Brunosol"])), 1)
        self.assertEqual(derive.texture_class(self.unit(["Vertisol", "Brunosol"])), 2)
        self.assertEqual(derive.texture_class(self.unit(["Brunosol", "Vertisol", "Litosol"])), 2)
        self.assertEqual(derive.texture_class(self.unit(["Litosol", "Regosol", "Vertisol"])), 0)  # a third order does not count
        self.assertEqual(derive.texture_class(self.unit([])), 1)
        self.assertEqual(derive.texture_class(None), 1)

    def test_capacity_grows_with_the_index_between_the_ends_and_is_one_at_the_middle(self):
        factors = [derive.capacity_factor(self.unit(["Brunosol"], i)) for i in (0, 50, 75, 100, 165, 230, 400)]
        self.assertEqual(factors, sorted(factors))
        self.assertEqual(factors[0], tables.constant("soil_capacity_low"))
        self.assertEqual(factors[3], 1.0)
        self.assertEqual(factors[-1], tables.constant("soil_capacity_high"))
        self.assertEqual(derive.capacity_factor(None), 1.0)
        self.assertEqual(derive.capacity_factor(self.unit(["Brunosol"], None)), 1.0)

    def test_the_satellite_error_follows_the_texture_and_is_the_same_every_time(self):
        light, medium, heavy = (derive.satellite_error(t, "f") for t in (0, 1, 2))
        self.assertGreater(light[0], medium[0])
        self.assertGreater(medium[0], heavy[0])
        self.assertLess(light[1], heavy[1])
        self.assertEqual(derive.satellite_error(1, "f"), derive.satellite_error(1, "f"))
        self.assertNotEqual(derive.satellite_error(1, "f"), derive.satellite_error(1, "g"))


class Port(unittest.TestCase):
    def test_no_soil_system_answers_nothing_and_the_registry_names_coneat(self):
        self.assertIsNone(NullSoilMap().lookup(-33.0, -58.0))
        self.assertEqual(set(SYSTEMS), {"none", "coneat"})

    def test_any_adapter_that_follows_the_port_fills_the_table(self):
        class Elsewhere:
            system = "other_country"

            def lookup(self, latitude, longitude):
                return SoilUnit("other_country", "A1", 50.0, ("Vertisol",)) if latitude < -33.5 else None
        fields = [{"field_id": "a", "latitude": "-34.0", "longitude": "-57.0"}, {"field_id": "b", "latitude": "-32.0", "longitude": "-57.0"}]
        rows = units.lookup_fields(Elsewhere(), fields)
        self.assertEqual([r["field_id"] for r in rows], ["a"])  # a field outside the map has no row
        self.assertEqual((rows[0]["system"], rows[0]["code"], rows[0]["dominant_orders"]), ("other_country", "A1", "Vertisol"))

    def test_the_committed_table_has_a_coneat_unit_for_every_field_of_the_panel(self):
        loaded = units.load()
        self.assertEqual(set(loaded), {r["field_id"] for r in tables.read("learning/fields")})
        self.assertEqual({u.system for u in loaded.values()}, {"coneat"})
        self.assertEqual(loaded["soriano"].code, "11.4")
        self.assertEqual({r["source_ref"] for r in tables.read("learning/soil_units")}, {"mgap_coneat"})

    @unittest.skipUnless(HAVE_LEARN, "numpy, scipy and scikit-learn are not installed")
    def test_without_a_soil_system_the_panel_still_works_with_medium_soils(self):
        from xmart_analysis.learning import fields
        with mock.patch.object(units, "load", return_value={}):
            everyone = fields.all_fields()
        self.assertEqual({f.clay for f in everyone}, {1})
        self.assertEqual({f.capacity_factor for f in everyone if not f.real}, {1.0})
        self.assertEqual({f.soil_unit for f in everyone}, {None})

    @unittest.skipUnless(HAVE_LEARN, "numpy, scipy and scikit-learn are not installed")
    def test_the_fields_take_their_soil_from_their_unit(self):
        from xmart_analysis.learning import fields
        by_id = {f.field_id: f for f in fields.all_fields()}
        self.assertEqual((by_id["sim_durazno"].clay, by_id["sim_salto"].clay), (0, 2))  # Litosol and Vertisol
        self.assertLess(by_id["sim_durazno"].capacity_factor, by_id["sim_rio_negro"].capacity_factor)  # index 57 against 219
        self.assertEqual(by_id["soriano"].capacity_factor, tables.constant("sensor_truth_capacity_factor"))  # stated by the table, not derived


@unittest.skipUnless(HAVE_CONEAT, "pyshp and pyproj are not installed")
class ConeatAdapter(unittest.TestCase):
    """The adapter on a small shapefile made here, in the map's projection (UTM 21S), so the 120 MB MGAP file is not needed."""

    @classmethod
    def setUpClass(cls):
        import shapefile
        from pyproj import Transformer
        cls.folder = tempfile.TemporaryDirectory()
        cls.inside = (-33.3577778, -58.078806)
        x, y = Transformer.from_crs(4326, 32721, always_xy=True).transform(cls.inside[1], cls.inside[0])
        box = lambda r: [[x - r, y - r], [x - r, y + r], [x + r, y + r], [x + r, y - r], [x - r, y - r]]  # noqa: E731
        path = str(Path(cls.folder.name) / "sue")
        with shapefile.Writer(path, shapeType=shapefile.POLYGON) as writer:
            writer.field("SC", "C", size=8)
            writer.poly([box(5000), box(1000)[::-1]])  # a square with a hole in the middle
            writer.record("07.1")
            writer.poly([box(1000)])
            writer.record("12.11")
        cls.path = path + ".shp"

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_a_point_gets_the_unit_of_its_polygon_and_the_hole_belongs_to_the_inner_one(self):
        from xmart_analysis.soils import ConeatMap
        soil_map = ConeatMap(self.path)
        ring = soil_map.lookup(self.inside[0] + 0.03, self.inside[1])  # about 3 km north: in the square, outside the hole
        centre = soil_map.lookup(*self.inside)
        self.assertEqual((ring.code, ring.productivity_index), ("7.1", 31.0))  # '07.1' on the map, '7.1' in the groups table
        self.assertEqual(centre.code, "12.11")
        self.assertEqual(centre.dominant_orders, ("Vertisol", "Brunosol"))

    def test_a_point_outside_every_polygon_has_no_unit_and_many_points_keep_their_order(self):
        from xmart_analysis.soils import ConeatMap
        soil_map = ConeatMap(self.path)
        found = soil_map.lookup_many([(-31.0, -55.0), self.inside, (self.inside[0] + 0.03, self.inside[1])])
        self.assertIsNone(found[0])
        self.assertEqual([u.code for u in found[1:]], ["12.11", "7.1"])

    def test_the_command_writes_the_units_of_the_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "units.csv"
            self.assertEqual(cli.main(["soil-units", "--system", "coneat", "--shapefile", self.path, "--out", str(out)]), 0)
            text = out.read_text(encoding="utf-8")
            self.assertIn("field_id,system,code,productivity_index,dominant_orders,source_ref", text)
            self.assertIn("soriano,coneat,12.11", text)  # only the Soriano coordinate falls inside the small test map

    def test_a_missing_library_is_a_clear_message_not_a_traceback(self):
        from xmart_analysis.soils import ConeatMap
        with mock.patch.dict("sys.modules", {"pyproj": None}):
            with self.assertRaises(ModuleNotFoundError) as caught:
                ConeatMap(self.path)
        self.assertIn("xmartagro-analysis[coneat]", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
