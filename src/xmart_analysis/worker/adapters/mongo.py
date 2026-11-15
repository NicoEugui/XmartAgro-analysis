"""MongoDB implementations of the ports. Collections: readings, inputs, results, jobs (shared with the API)."""

from datetime import timedelta

from ..domain import Job, Reading


def connect(settings):
    from pymongo import MongoClient

    options = {"appName": "xmartagro-analysis-worker", "tz_aware": True, "serverSelectionTimeoutMS": 5000}
    if settings.mongo_username and settings.mongo_password:
        options.update(username=settings.mongo_username, password=settings.mongo_password)
    return MongoClient(settings.mongo_uri, **options)[settings.mongo_db]


class MongoReadings:
    def __init__(self, db):
        self.collection = db["readings"]

    @staticmethod
    def _reading(doc):
        return Reading(doc["field_id"], doc["sensor_id"], doc["moisture"], doc["sensor_type"], doc["received_at"])

    def latest(self, field_id):
        doc = self.collection.find_one({"field_id": field_id}, sort=[("received_at", -1)])
        return self._reading(doc) if doc else None

    def history(self, field_id, limit):
        """The last `limit` readings of the field, oldest first."""
        docs = self.collection.find({"field_id": field_id}, sort=[("received_at", -1)], limit=limit)
        return [self._reading(d) for d in reversed(list(docs))]


class MongoInputs:
    def __init__(self, db):
        self.collection = db["inputs"]

    def get(self, field_id):
        return self.collection.find_one({"_id": field_id})


class MongoResults:
    def __init__(self, db):
        self.collection = db["results"]

    def current_hash(self, field_id):
        doc = self.collection.find_one({"_id": field_id}, projection={"inputs_hash": 1})
        return doc.get("inputs_hash") if doc else None

    def save(self, field_id, document):
        self.collection.replace_one({"_id": field_id}, document, upsert=True)


class MongoJobQueue:
    def __init__(self, db, stale_after=timedelta(minutes=15)):
        self.collection, self.stale_after = db["jobs"], stale_after

    def claim(self, now):
        from pymongo import ReturnDocument

        doc = self.collection.find_one_and_update(
            {"$or": [{"status": "pending"}, {"status": "running", "claimed_at": {"$lt": now - self.stale_after}}]},
            {"$set": {"status": "running", "claimed_at": now}, "$inc": {"attempts": 1}},
            sort=[("requested_at", 1)], return_document=ReturnDocument.AFTER)
        if not doc:
            return None
        return Job(str(doc["_id"]), doc["field_id"], doc["attempts"], doc["requested_at"], now)

    def _key(self, job):
        from bson import ObjectId

        return {"_id": ObjectId(job.id) if len(job.id) == 24 else job.id}

    def complete(self, job, now):
        self.collection.update_one(self._key(job), {"$set": {"status": "done", "finished_at": now, "error": None}})
        self.collection.update_many(
            {"field_id": job.field_id, "status": "pending", "requested_at": {"$lte": job.claimed_at}},
            {"$set": {"status": "done", "finished_at": now, "error": {"code": "superseded"}}})

    def release(self, job, error):
        self.collection.update_one(self._key(job), {"$set": {"status": "pending", "error": error}})

    def fail(self, job, error, now):
        self.collection.update_one(self._key(job), {"$set": {"status": "failed", "finished_at": now, "error": error}})
