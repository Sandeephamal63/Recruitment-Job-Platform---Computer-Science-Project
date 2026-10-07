from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.client_session import ClientSession
from pymongo.database import Database

SCORE_BAND_BOUNDARIES = [0, 20, 40, 60, 80, 101]
SCORE_BAND_LABELS = ["0-19", "20-39", "40-59", "60-79", "80-100"]
PENDING_BAND_LABEL = "not scored"

# ``$bucket`` reports the band's lower boundary, not a label, so the boundary to
# label mapping is resolved here — the same place the boundaries are defined.
BOUNDARY_BANDS = dict(zip(SCORE_BAND_BOUNDARIES[:-1], SCORE_BAND_LABELS))

SORT_SPECS = {
    "newest": {"submittedAt": -1},
    "oldest": {"submittedAt": 1},
}


class ApplicationRepository:
    def __init__(self, db: Database):
        self._collection = db.applications

    def create(self, application: dict, session: ClientSession | None = None) -> str:
        return str(self._collection.insert_one(application, session=session).inserted_id)

    def find_by_id(self, application_id: str) -> Optional[dict]:
        try:
            return self._collection.find_one({"_id": ObjectId(application_id)})
        except Exception:
            return None

    def find_by_candidate(self, candidate_id: str) -> list[dict]:
        return list(
            self._collection.find({"candidateId": ObjectId(candidate_id)}).sort("submittedAt", -1)
        )

    def find_duplicate(self, job_id: str, candidate_id: str) -> Optional[dict]:
        return self._collection.find_one(
            {"jobId": ObjectId(job_id), "candidateId": ObjectId(candidate_id)}
        )

    def find_by_job(self, job_id: str) -> list[dict]:
        return list(
            self._collection.find({"jobId": ObjectId(job_id)}).sort("submittedAt", -1)
        )

    def find_by_job_ids(self, job_ids: list[str]) -> list[dict]:
        object_ids = _object_ids(job_ids)
        if not object_ids:
            return []
        return list(self._collection.find({"jobId": {"$in": object_ids}}))

    def page_for_job(
        self,
        job_id: str,
        status: str | None,
        min_score: int | None,
        sort: str,
        page: int,
        page_size: int,
    ) -> tuple[list[dict], int]:
        """One page of a job's applicants plus the total match count.

        ``matchScore`` lives in ``matchResults``, so sorting and minimum-score
        filtering need a join. It happens here in a single aggregate with
        ``$lookup`` against the unique ``applicationId`` index, which keeps the
        repository the only place that knows the collections are related.

        Unscored applications (score still ``null``) are pushed to the end of
        every score ordering rather than being treated as 0, so a pending match
        never masquerades as a poor one.
        """
        match: dict = {"jobId": ObjectId(job_id)}
        if status:
            match["status"] = status

        sentinel = -1 if sort == "score-desc" else 101
        pipeline: list[dict] = [
            {"$match": match},
            {
                "$lookup": {
                    "from": "matchResults",
                    "localField": "_id",
                    "foreignField": "applicationId",
                    "as": "_joinedMatch",
                }
            },
            {
                "$addFields": {
                    "match": {"$arrayElemAt": ["$_joinedMatch", 0]},
                    "_scoreSort": {
                        "$ifNull": [{"$arrayElemAt": ["$_joinedMatch.matchScore", 0]}, sentinel]
                    },
                }
            },
        ]
        if min_score is not None:
            pipeline.append(
                {
                    "$match": {
                        "match.matchScore": {"$gte": min_score},
                    }
                }
            )
        if sort in SORT_SPECS:
            pipeline.append({"$sort": SORT_SPECS[sort]})
        else:
            direction = -1 if sort == "score-desc" else 1
            pipeline.append({"$sort": {"_scoreSort": direction, "submittedAt": -1}})

        pipeline.append(
            {
                "$facet": {
                    "items": [{"$skip": (page - 1) * page_size}, {"$limit": page_size}],
                    "total": [{"$count": "count"}],
                }
            }
        )
        pipeline.append({"$project": {"_joinedMatch": 0, "_scoreSort": 0}})

        result = next(iter(self._collection.aggregate(pipeline)), {"items": [], "total": []})
        total = result["total"][0]["count"] if result["total"] else 0
        return result["items"], total

    def funnel_by_job(self, job_ids: list[str]) -> dict[str, dict[str, int]]:
        """``{jobId: {status: count}}`` for every stage, in one aggregation."""
        object_ids = _object_ids(job_ids)
        if not object_ids:
            return {}
        pipeline = [
            {"$match": {"jobId": {"$in": object_ids}}},
            {"$group": {"_id": {"jobId": "$jobId", "status": "$status"}, "count": {"$sum": 1}}},
        ]
        funnel: dict[str, dict[str, int]] = {str(job_id): {} for job_id in job_ids}
        for row in self._collection.aggregate(pipeline):
            funnel.setdefault(str(row["_id"]["jobId"]), {})[row["_id"]["status"]] = row["count"]
        return funnel

    def score_distribution(self, job_ids: list[str]) -> list[dict]:
        """Histogram of match scores across the given jobs' applicant pools.

        Returns ``[{"band": "60-79", "count": 4}, ...]`` with the pending rows
        collapsed into a single ``not scored`` bucket rather than dropped, so the
        employer can see that scoring is still catching up. Bands with no
        applicants are omitted; the service is what guarantees a gap-free
        ordering for display.
        """
        object_ids = _object_ids(job_ids)
        if not object_ids:
            return []
        pipeline = [
            {"$match": {"jobId": {"$in": object_ids}}},
            {
                "$lookup": {
                    "from": "matchResults",
                    "localField": "_id",
                    "foreignField": "applicationId",
                    "as": "_joinedMatch",
                }
            },
            {"$addFields": {"matchScore": {"$arrayElemAt": ["$_joinedMatch.matchScore", 0]}}},
            {
                "$bucket": {
                    "groupBy": "$matchScore",
                    "boundaries": SCORE_BAND_BOUNDARIES,
                    "default": PENDING_BAND_LABEL,
                    "output": {"count": {"$sum": 1}},
                }
            },
        ]
        return [
            {
                "band": BOUNDARY_BANDS.get(bucket["_id"], PENDING_BAND_LABEL),
                "count": bucket["count"],
            }
            for bucket in self._collection.aggregate(pipeline)
        ]

    def update_status(
        self,
        application_id: str,
        status: str,
        now,
        rejection_reason: str | None = None,
    ) -> Optional[dict]:
        updates: dict = {"status": status, "updatedAt": now}
        if rejection_reason is not None:
            updates["rejectionReason"] = rejection_reason
        elif status != "rejected":
            updates["rejectionReason"] = None
        self._collection.update_one({"_id": ObjectId(application_id)}, {"$set": updates})
        return self.find_by_id(application_id)

    def update_status_many(
        self,
        application_ids: list[str],
        status: str,
        now,
        rejection_reason: str | None = None,
    ) -> list[dict]:
        object_ids = _object_ids(application_ids)
        if not object_ids:
            return []
        updates: dict = {"status": status, "updatedAt": now, "rejectionReason": rejection_reason}
        self._collection.update_many({"_id": {"$in": object_ids}}, {"$set": updates})
        return list(self._collection.find({"_id": {"$in": object_ids}}))

    def add_note(self, application_id: str, note: dict) -> Optional[dict]:
        self._collection.update_one(
            {"_id": ObjectId(application_id)},
            {"$push": {"notes": note}, "$set": {"updatedAt": note["createdAt"]}},
        )
        return self.find_by_id(application_id)

    def remove_note(self, application_id: str, note_id: str) -> Optional[dict]:
        try:
            note_object_id = ObjectId(note_id)
        except InvalidId:
            raise ValueError(note_id)
        self._collection.update_one(
            {"_id": ObjectId(application_id)},
            {"$pull": {"notes": {"id": note_object_id}}},
        )
        return self.find_by_id(application_id)

    def average_score(self, job_ids: list[str]) -> float | None:
        """Mean match score across the given jobs' applicant pools.

        ``None`` when nothing has been scored yet, so the dashboard can render
        "not scored" instead of a misleading 0. Pending placeholder rows carry a
        null ``matchScore`` and are skipped by the average.
        """
        object_ids = _object_ids(job_ids)
        if not object_ids:
            return None
        pipeline = [
            {"$match": {"jobId": {"$in": object_ids}}},
            {
                "$lookup": {
                    "from": "matchResults",
                    "localField": "_id",
                    "foreignField": "applicationId",
                    "as": "_joinedMatch",
                }
            },
            {"$addFields": {"matchScore": {"$arrayElemAt": ["$_joinedMatch.matchScore", 0]}}},
            {"$match": {"matchScore": {"$ne": None}}},
            {"$group": {"_id": None, "average": {"$avg": "$matchScore"}}},
        ]
        rows = list(self._collection.aggregate(pipeline))
        return round(rows[0]["average"], 1) if rows else None

    def counts_by_job(self, job_ids: list[str]) -> dict[str, int]:
        """Total applications per job, derived from the same funnel aggregation."""
        return {
            job_id: sum(stages.values())
            for job_id, stages in self.funnel_by_job(job_ids).items()
        }


def _object_ids(ids: list[str]) -> list[ObjectId]:
    object_ids: list[ObjectId] = []
    for identifier in ids:
        try:
            object_ids.append(ObjectId(identifier))
        except Exception:
            continue
    return object_ids
