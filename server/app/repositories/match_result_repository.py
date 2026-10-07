from typing import Optional

from bson import ObjectId
from pymongo.client_session import ClientSession
from pymongo.database import Database

from ..utils.time import utcnow


class MatchResultRepository:
    def __init__(self, db: Database):
        self._collection = db.matchResults

    def create_placeholder(self, application_id, now, session: ClientSession | None = None) -> None:
        self._collection.insert_one(
            {
                "applicationId": application_id,
                "matchScore": None,
                "matchedSkills": [],
                "missingSkills": [],
                "recommendations": [],
                "modelVersion": "pending",
                "createdAt": now,
            },
            session=session,
        )

    def find_by_application(self, application_id: str) -> Optional[dict]:
        try:
            return self._collection.find_one({"applicationId": ObjectId(application_id)})
        except Exception:
            return None

    def find_by_application_ids(self, application_ids: list[str]) -> dict[str, dict]:
        object_ids = []
        for application_id in application_ids:
            try:
                object_ids.append(ObjectId(application_id))
            except Exception:
                continue
        if not object_ids:
            return {}
        results = self._collection.find({"applicationId": {"$in": object_ids}})
        return {str(result["applicationId"]): result for result in results}

    def upsert_result(self, application_id: str, result: dict) -> None:
        """Fill in (or replace) the result for an application, keeping ``createdAt``.

        The M3 placeholder row has the same ``applicationId``; updating it in
        place honours the ``{applicationId}`` unique index.
        """
        application_oid = ObjectId(application_id)
        self._collection.update_one(
            {"applicationId": application_oid},
            {
                "$set": {**result, "applicationId": application_oid},
                "$setOnInsert": {"createdAt": utcnow()},
            },
            upsert=True,
        )

    def reset_to_pending(self, application_ids: list[str]) -> int:
        """Invalidate stored scores for the given applications.

        Called when an employer edits ``requiredSkills``: the previous score was
        computed against a different job definition, so leaving it in place would
        show a confidently wrong number. Rows are reset to the same ``pending``
        sentinel the create path uses, which the read path already knows how to
        materialise lazily on the next read.

        ``createdAt`` is deliberately left alone — it records when the analysis
        was first requested for the application, not which revision of the job
        it was run against.
        """
        object_ids = []
        for application_id in application_ids:
            try:
                object_ids.append(ObjectId(application_id))
            except Exception:
                continue
        if not object_ids:
            return 0
        result = self._collection.update_many(
            {"applicationId": {"$in": object_ids}},
            {
                "$set": {
                    "matchScore": None,
                    "matchedSkills": [],
                    "missingSkills": [],
                    "recommendations": [],
                    "modelVersion": "pending",
                }
            },
        )
        return result.modified_count