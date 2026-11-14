"""Engine session to the `results` document the API serves (summary, scenarios and the full bilingual analysis)."""

import hashlib
import json

from xmart_analysis.engine.i18n import LANGUAGES, resolve
from xmart_analysis.frontend import payload

SCHEMA_VERSION = "1.0"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def to_results(field_id, session, inputs_hash, generated_at, engine_version, language, notes):
    parts = payload.api_parts(session, generated_at)
    return {
        "_id": field_id, "schema_version": SCHEMA_VERSION, "inputs_hash": inputs_hash, "engine_version": engine_version,
        "generated_at": generated_at.isoformat(), "mapping_notes": list(notes),
        "summary": resolve(parts["summary"], language), "scenarios": resolve(parts["scenarios"], language),
        "analysis": {lang: resolve(session, lang) for lang in LANGUAGES},
    }
