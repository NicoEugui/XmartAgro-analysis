"""Structured engine errors for the frontend.

Every deliberate rejection is an EngineError (a ValueError) with a stable `code`, the offending `field`, a
human-readable message and optional details. `call()` is the entry point a UI should use: it never raises,
and an unexpected failure is reported as `internal_error` instead of leaking a KeyError or TypeError.
"""


class EngineError(ValueError):
    def __init__(self, code, field, message, **details):
        super().__init__(message)
        self.code, self.field, self.message, self.details = code, field, message, details

    def to_dict(self):
        return {"code": self.code, "field": self.field, "message": self.message, "details": self.details}


def call(fn, *args, **kwargs):
    """Run an engine function; return {"ok": True, "result": ...} or {"ok": False, "error": {...}}."""
    try:
        return {"ok": True, "result": fn(*args, **kwargs)}
    except EngineError as exc:
        return {"ok": False, "error": exc.to_dict()}
    except Exception as exc:  # noqa: BLE001 - the UI must never see a raw exception
        return {"ok": False, "error": {"code": "internal_error", "field": None,
                                       "message": "Unexpected engine failure", "details": {"type": type(exc).__name__}}}
