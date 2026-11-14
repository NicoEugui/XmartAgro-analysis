"""Label catalog tests: every key has English and Spanish text, params resolve, outputs match in structure."""
import json
import re
import unittest

from xmart_analysis.engine import i18n as i18n
import fixtures
from xmart_analysis.engine import platform_session as ps

def shape(obj):
    if isinstance(obj, dict):
        return {k: shape(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [shape(v) for v in obj]
    return type(obj).__name__


class Catalog(unittest.TestCase):
    def test_every_entry_has_both_languages_and_text(self):
        for key, entry in i18n.catalog().items():
            self.assertEqual(set(entry), {"en", "es"}, key)
            self.assertTrue(entry["en"].strip() and entry["es"].strip(), key)

    def test_placeholders_match_between_languages(self):
        for key, entry in i18n.catalog().items():
            self.assertEqual(sorted(re.findall(r"\{(\w+)\}", entry["en"])),
                             sorted(re.findall(r"\{(\w+)\}", entry["es"])), key)

    def test_label_substitutes_nested_labels_per_language(self):
        crop = i18n.label("crops.maize.name")
        out = i18n.label("sowing.warning.far_from_reading", days=crop)
        self.assertIn(crop["en"], out["en"])
        self.assertIn(crop["es"], out["es"])

    def test_missing_key_fails(self):
        with self.assertRaises(KeyError):
            i18n.label("no.such.key")

    def test_resolve_leaves_no_label_objects(self):
        data = {"a": [i18n.label("crops.maize.name")], "b": {"c": i18n.label("crops.wheat.name")}}
        self.assertEqual(i18n.resolve(data, "es"), {"a": ["Maíz de primera"], "b": {"c": "Trigo"}})


class Outputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session = ps.build_session(fixtures.default_answers())
        cls.docs = {lang: i18n.resolve(cls.session, lang) for lang in ("en", "es")}

    def test_both_languages_have_the_same_structure(self):
        self.assertEqual(shape(self.docs["en"]), shape(self.docs["es"]))

    def test_numbers_are_identical_in_both_languages(self):
        def numbers(obj):
            if isinstance(obj, dict):
                return {k: numbers(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [numbers(v) for v in obj]
            return obj if isinstance(obj, (int, float, bool)) or obj is None else "text"
        self.assertEqual(numbers(self.docs["en"]), numbers(self.docs["es"]))

    def test_spanish_output_is_actually_translated(self):
        en, es = (self.docs[l]["outputs"]["main_screen"]["scenarios"]["note"] for l in ("en", "es"))
        self.assertNotEqual(en, es)

    def test_no_label_object_is_left_unresolved(self):
        self.assertNotIn('"key":', json.dumps(self.docs["es"]))


if __name__ == "__main__":
    unittest.main()
