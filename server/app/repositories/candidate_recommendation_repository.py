from datetime import datetime

from bson import ObjectId
from pymongo.database import Database

# One cache document per candidate (enforced by the unique index on
# ``candidateId`` in ``db.INDEX_SPECS``), so the recommender can be a pure
# single-document upsert rather than a read-then-write race between two
# dashboard loads recomputing at the same time.


class CandidateRecommendationRepository:
    def __init__(self, db: Database):
        self._collection = db.candidateRecommendations

    def find_by_candidate(self, candidate_id: str) -> dict | None:
        try:
            return self._collection.find_one({"candidateId": ObjectId(candidate_id)})
        except Exception:
            return None

    def upsert(
        self, candidate_id: str, recommendations: list[dict], now: datetime
    ) -> dict:
        """Replace a candidate's cached ranking with a freshly computed one.

        ``createdAt`` is set on insert only, so a recompute records when the
        ranking last changed without losing when the cache row was created.
        """
        self._collection.update_one(
            {"candidateId": ObjectId(candidate_id)},
            {
                "$set": {"recommendations": recommendations, "computedAt": now},
                "$setOnInsert": {"candidateId": ObjectId(candidate_id), "createdAt": now},
            },
            upsert=True,
        )
        return {
            "recommendations": recommendations,
            "computedAt": now,
        }
