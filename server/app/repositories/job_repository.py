from datetime import datetime
from typing import Optional

from bson import ObjectId
from pymongo.database import Database

from ..utils.time import utcnow

SORT_SPECS = {
    "newest": {"createdAt": -1},
    "oldest": {"createdAt": 1},
    "title": {"title": 1},
}

# Every read except the recommender's projects the vector out. A stored
# embedding is 384 doubles, so leaving it on a page of 12 browse results would
# ship ~70KB per request that no response field ever uses. Only
# ``find_open_with_embeddings`` asks for it.
WITHOUT_EMBEDDING = {"embedding": 0}


def not_expired_clause(now: datetime) -> dict:
    """The "still accepting applications" half of the open-job predicate.

    ``status`` alone is not enough: a posting whose deadline has passed is
    closed by the passage of time, not by the employer, and both browse and the
    recommender must agree that it can no longer be applied to.

    ``{"deadline": None}`` matches an explicit null *and* a missing field in
    Mongo, which is what keeps every posting written before deadlines existed
    open. Because a deadline is stored at the end of the day it names
    (``utils.time.end_of_day``), "still open" is exactly ``deadline >= now`` —
    no date truncation, and no local-time conversion on either side.
    """
    return {"$or": [{"deadline": None}, {"deadline": {"$gte": now}}]}


def open_job_filter(now: datetime | None = None) -> dict:
    """The complete predicate for a posting that is still open and live.

    The single declaration of what "open" means at the storage layer. Every
    read of the open-job corpus goes through here, so browse, the recommender
    and the pagination total cannot disagree about which vacancies are live.

    Merged with caller-supplied filters by key, so a caller's ``query`` must not
    carry its own ``status`` or top-level ``$or`` — a later key silently wins,
    and that is exactly how expiry would be dropped from browse without any
    error.
    """
    return {"status": "open", **not_expired_clause(now or utcnow())}


class JobRepository:
    def __init__(self, db: Database):
        self._collection = db.jobs

    def create(self, job: dict) -> str:
        return str(self._collection.insert_one(job).inserted_id)

    def find_by_id(self, job_id: str) -> Optional[dict]:
        try:
            return self._collection.find_one(
                {"_id": ObjectId(job_id)}, WITHOUT_EMBEDDING
            )
        except Exception:
            return None

    def find_by_employer(self, employer_id: str) -> list[dict]:
        return list(
            self._collection.find({"employerId": ObjectId(employer_id)}, WITHOUT_EMBEDDING).sort(
                "createdAt", -1
            )
        )

    def find_by_ids(self, job_ids: list) -> list[dict]:
        object_ids = []
        for job_id in job_ids:
            try:
                object_ids.append(ObjectId(job_id))
            except Exception:
                continue
        if not object_ids:
            return []
        return list(self._collection.find({"_id": {"$in": object_ids}}, WITHOUT_EMBEDDING))

    def find_open_with_embeddings(self, now: datetime | None = None) -> list[dict]:
        """Open jobs *including* their stored embedding.

        The one read that needs the vector, used by the candidate recommender to
        score a profile against the whole open-job corpus without re-encoding
        any posting. Jobs written before embeddings existed come back without
        the field; the scorer falls back to TF-IDF for those rather than
        dropping them, and ``make db-embeddings`` backfills them.

        Expired postings are excluded for the same reason browse excludes them:
        recommending a role that can no longer be applied to is worse than
        recommending nothing.
        """
        return list(self._collection.find(open_job_filter(now)))

    def page_open(
        self,
        query: dict,
        sort: str,
        page: int,
        page_size: int,
        now: datetime | None = None,
    ) -> tuple[list[dict], int]:
        """One page of open jobs plus the total match count.

        Uses ``$facet`` so the page and the total come from a single round trip
        — a separate ``count_documents`` would race with the page query and cost
        a second index scan.

        This method owns the "is open" predicate, so a caller cannot forget the
        expiry half of it. The consequence is that a caller-supplied ``query``
        must not carry its own top-level ``$or`` or a ``status`` of its own — see
        :func:`open_job_filter`.
        """
        match = {**open_job_filter(now), **query}
        pipeline = [
            {"$match": match},
            {"$sort": SORT_SPECS.get(sort, SORT_SPECS["newest"])},
            {
                "$facet": {
                    "items": [
                        {"$project": WITHOUT_EMBEDDING},
                        {"$skip": (page - 1) * page_size},
                        {"$limit": page_size},
                    ],
                    "total": [{"$count": "count"}],
                }
            },
        ]
        result = next(iter(self._collection.aggregate(pipeline)), {"items": [], "total": []})
        total = result["total"][0]["count"] if result["total"] else 0
        return result["items"], total

    def update(self, job_id: str, updates: dict) -> Optional[dict]:
        self._collection.update_one({"_id": ObjectId(job_id)}, {"$set": updates})
        return self.find_by_id(job_id)
