import argparse
import logging
from datetime import datetime, timedelta, timezone

from .adapters.engine import EngineAnalyzer
from .adapters.mongo import MongoInputs, MongoJobQueue, MongoReadings, MongoResults, connect
from .application import RunAnalysis
from .config import Settings
from .worker import Worker


def build(settings):
    db = connect(settings)
    clock = lambda: datetime.now(timezone.utc)  # noqa: E731
    run = RunAnalysis(MongoReadings(db), MongoInputs(db), MongoResults(db), EngineAnalyzer(), settings, clock)
    queue = MongoJobQueue(db, timedelta(minutes=settings.stale_job_minutes))
    return Worker(queue, run, settings, clock)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="xmart-analysis-worker", description="Background analysis worker")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="process pending jobs, then exit (default)")
    mode.add_argument("--loop", action="store_true", help="keep polling for jobs")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings.from_env()
    if not settings.mongo_uri:
        parser.error("MONGODB_URI is not set")
    worker = build(settings)
    if args.loop:
        worker.run_forever()
    else:
        logging.getLogger("analysis_worker").info("processed %d job(s)", worker.run_until_idle())


if __name__ == "__main__":
    main()
