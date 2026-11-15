from xmart_analysis.engine import tables
from xmart_analysis.engine.errors import EngineError

from .domain import Outcome
from .mapping.inputs import to_answers
from .mapping.results import digest, to_results
from .mapping.sensor import to_sensor_info


class RunAnalysis:
    """Use case: analyze one field from its latest reading and stored inputs, skipping unchanged work."""

    def __init__(self, readings, inputs, results, analyzer, settings, clock):
        self.readings, self.inputs, self.results = readings, inputs, results
        self.analyzer, self.settings, self.clock = analyzer, settings, clock

    def prepare(self, field_id):
        """Everything the analysis needs, without running it: (answers, sensor_info, notes, now, inputs hash)."""
        reading = self.readings.latest(field_id)
        if reading is None:
            raise EngineError("no_reading", "sensor", f"Field '{field_id}' has no sensor reading yet", field_id=field_id)
        now = self.clock()
        answers, notes = to_answers(self.inputs.get(field_id), reading, self.settings.comparison)
        sensor_info = to_sensor_info(reading, now, self.readings.history(field_id, tables.constant("sensor_days")))
        key = digest({"answers": answers, "sensor": sensor_info, "engine": self.analyzer.version})
        return answers, sensor_info, notes, now, key

    def __call__(self, field_id):
        answers, sensor_info, notes, now, key = self.prepare(field_id)
        if self.results.current_hash(field_id) == key:
            return Outcome("unchanged", key, notes)
        session = self.analyzer.analyze(answers, sensor_info)
        document = to_results(field_id, session, key, now, self.analyzer.version, self.settings.ui_language, notes)
        self.results.save(field_id, document)
        return Outcome("computed", key, notes)
