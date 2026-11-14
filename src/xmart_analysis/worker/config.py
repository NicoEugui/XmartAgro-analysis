import os
from dataclasses import dataclass

from xmart_analysis.engine import rotations

# What is compared until the panel lets a person pick: the rotations the surveyed producers reported.
DEFAULT_COMPARISON = tuple({"kind": "rotation", "rotation": rotation_id} for rotation_id in rotations.ids())


@dataclass(frozen=True)
class Settings:
    mongo_uri: str | None = None
    mongo_username: str | None = None
    mongo_password: str | None = None
    mongo_db: str = "Xmart-Agro"
    poll_seconds: float = 5.0
    stale_job_minutes: int = 15
    max_attempts: int = 3
    ui_language: str = "es"
    comparison: tuple = DEFAULT_COMPARISON

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        return cls(mongo_uri=env.get("MONGODB_URI"), mongo_username=env.get("MONGODB_USERNAME"),
                   mongo_password=env.get("MONGODB_PASSWORD"), mongo_db=env.get("MONGODB_DB", cls.mongo_db),
                   poll_seconds=float(env.get("WORKER_POLL_SECONDS", cls.poll_seconds)),
                   stale_job_minutes=int(env.get("WORKER_STALE_JOB_MINUTES", cls.stale_job_minutes)),
                   max_attempts=int(env.get("WORKER_MAX_ATTEMPTS", cls.max_attempts)),
                   ui_language=env.get("WORKER_UI_LANGUAGE", cls.ui_language))
