import hashlib

from xmart_analysis.engine import platform_session as ps
from xmart_analysis.engine import context
from xmart_analysis.engine import tables
from xmart_analysis.engine import water_model as wm


class EngineAnalyzer:
    """Runs the water-balance engine; the climate and calibration context is built once and reused."""

    def __init__(self):
        self._context = None
        self.version = self._version()

    @staticmethod
    def _version():
        calibration = wm.CALIBRATION_PATH.read_bytes()
        return f"1.1-{tables.active_site()}-{hashlib.sha256(calibration).hexdigest()[:12]}"

    def analyze(self, answers, sensor_info):
        if self._context is None:
            self._context = context.build_context()
        return ps.build_session(answers, sensor_info=sensor_info, context=self._context)
