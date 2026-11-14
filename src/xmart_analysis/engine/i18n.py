"""Bilingual labels (English and Spanish) for everything the model shows to people.

Code, data keys and enumerated values are English. Display text lives in i18n/labels.json and is
referenced by a stable key. `label()` returns {"key", "en", "es"} so a JSON consumer can pick a
language without a second lookup. A param may itself be a label: it is substituted per language.
"""

import json
from pathlib import Path

LANGUAGES = ("en", "es")
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_CATALOG = {}
for _name in ("labels.json", "report_labels.json"):  # engine texts, then the texts only figures need
    _CATALOG.update(json.loads((DATA_DIR / _name).read_text(encoding="utf-8")))


def catalog():
    return _CATALOG


def label(key, **params):
    """Return {"key": key, "en": ..., "es": ...}; raise KeyError if the key or a language is missing."""
    entry = _CATALOG[key]
    out = {"key": key}
    for lang in LANGUAGES:
        values = {name: (v[lang] if isinstance(v, dict) and lang in v else v) for name, v in params.items()}
        out[lang] = entry[lang].format(**values) if values else entry[lang]
    return out


def resolve(obj, lang):
    """Replace every label object {"key", "en", "es"} inside obj with its text in `lang`."""
    if isinstance(obj, dict):
        if set(obj) == {"key", *LANGUAGES}:
            return obj[lang]
        return {k: resolve(v, lang) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve(v, lang) for v in obj]
    return obj
