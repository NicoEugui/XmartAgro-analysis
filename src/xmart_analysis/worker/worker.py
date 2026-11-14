import logging
import time

from xmart_analysis.engine.errors import EngineError

log = logging.getLogger("analysis_worker")


class Worker:
    """Claims jobs and runs the analysis. Engine errors are final; anything else is retried up to max_attempts."""

    def __init__(self, queue, run, settings, clock, sleep=time.sleep):
        self.queue, self.run, self.settings, self.clock, self.sleep = queue, run, settings, clock, sleep

    def run_once(self):
        job = self.queue.claim(self.clock())
        if job is None:
            return False
        try:
            outcome = self.run(job.field_id)
        except EngineError as exc:
            log.warning("job %s failed: %s", job.id, exc.code)
            self.queue.fail(job, exc.to_dict(), self.clock())
        except Exception as exc:  # noqa: BLE001 - one bad job must not stop the worker
            log.exception("job %s crashed", job.id)
            error = {"code": "internal_error", "field": None, "message": "Unexpected failure",
                     "details": {"type": type(exc).__name__}}
            if job.attempts >= self.settings.max_attempts:
                self.queue.fail(job, error, self.clock())
            else:
                self.queue.release(job, error)
        else:
            log.info("job %s field=%s %s", job.id, job.field_id, outcome.status)
            self.queue.complete(job, self.clock())
        return True

    def run_until_idle(self):
        count = 0
        while self.run_once():
            count += 1
        return count

    def run_forever(self, should_stop=lambda: False):
        while not should_stop():
            if not self.run_once():
                self.sleep(self.settings.poll_seconds)
