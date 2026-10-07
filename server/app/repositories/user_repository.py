from bson import ObjectId
from pymongo.database import Database

# A stored profile embedding is 384 doubles and no response field uses it, so
# every general read projects it out and the recommender's embedding read is the
# only caller that asks for it. See ``JobRepository.WITHOUT_EMBEDDING`` for the
# same reasoning applied to job vectors.
WITHOUT_PROFILE_EMBEDDING = {"profileEmbedding": 0}


class UserRepository:
    """Read/write access to the ``users`` collection (repos are the only place
    Mongo queries live; M1 auth predates the pattern, wired here from M6)."""

    def __init__(self, db: Database):
        self._collection = db.users

    def find_by_ids(self, user_ids: list[str]) -> list[dict]:
        object_ids = []
        for user_id in user_ids:
            object_id = self._parse(user_id)
            if object_id is not None:
                object_ids.append(object_id)
        if not object_ids:
            return []
        return list(self._collection.find({"_id": {"$in": object_ids}}, WITHOUT_PROFILE_EMBEDDING))

    def find_by_email(self, email: str) -> dict | None:
        return self._collection.find_one({"email": email})

    def find_by_id(self, user_id: str) -> dict | None:
        object_id = self._parse(user_id)
        if object_id is None:
            return None
        return self._collection.find_one({"_id": object_id}, WITHOUT_PROFILE_EMBEDDING)

    def find_profile_embedding(self, user_id: str) -> dict | None:
        """The candidate's cached profile vector and the cache-validity stamps.

        Split out from :meth:`find_by_id` so the recommender can re-use a stored
        vector without every other user read paying for it. The two stamps come
        back with it so one round trip answers "is this vector still valid?".
        """
        object_id = self._parse(user_id)
        if object_id is None:
            return None
        return self._collection.find_one(
            {"_id": object_id},
            {
                "profileEmbedding": 1,
                "profileEmbeddingModel": 1,
                "profileUpdatedAt": 1,
                "createdAt": 1,
            },
        )

    def create(self, document: dict) -> str:
        return str(self._collection.insert_one(document).inserted_id)

    def update(self, user_id: str, updates: dict) -> dict | None:
        object_id = self._parse(user_id)
        if object_id is None:
            return None
        self._collection.update_one({"_id": object_id}, {"$set": updates})
        return self._collection.find_one({"_id": object_id})

    def add_saved_job(self, user_id: str, job_id: ObjectId) -> dict | None:
        """Idempotent bookmark: ``$addToSet`` makes a repeated save a no-op
        instead of duplicating the entry."""
        self._collection.update_one({"_id": ObjectId(user_id)}, {"$addToSet": {"savedJobIds": job_id}})
        return self.find_by_id(user_id)

    def remove_saved_job(self, user_id: str, job_id: ObjectId) -> dict | None:
        self._collection.update_one({"_id": ObjectId(user_id)}, {"$pull": {"savedJobIds": job_id}})
        return self.find_by_id(user_id)

    @staticmethod
    def _parse(user_id: str) -> ObjectId | None:
        try:
            return ObjectId(user_id)
        except Exception:
            return None