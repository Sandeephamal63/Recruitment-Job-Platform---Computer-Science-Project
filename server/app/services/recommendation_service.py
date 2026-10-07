"""Proactive job recommendations for a candidate.

The counterpart to :mod:`app.services.match_service`, which scores a CV against
the single job it was submitted to. This slice scores a candidate profile
against *every* open job and ranks the result onto the candidate dashboard.

Two properties are load-bearing:

* **One score path.** Scoring is delegated to
  :func:`app.services.matching_service.score_candidate_against_jobs`, which
  shares its blend with the per-application scorer, so a job's dashboard score
  equals its post-application score.
* **Jobs are never re-encoded per request.** Each job's embedding is computed
  once, when the posting is created or its text edited. The candidate's own
  profile vector is cached on the user document for the same reason.

The ranking itself is cached per candidate in ``candidateRecommendations`` and
invalidated by comparing ``computedAt`` against ``users.profileUpdatedAt``, the
stamp that moves whenever the candidate's CV or skills change. Job edits do not
invalidate the cache — a stale ranking self-heals the next time the candidate's
profile changes, which is the accepted trade-off of a cache that is not
recomputed on every job posting.
"""

from datetime import datetime
from typing import Any, Optional

from ..repositories.candidate_recommendation_repository import (
    CandidateRecommendationRepository,
)
from ..repositories.job_repository import JobRepository
from ..repositories.user_repository import UserRepository
from ..schemas.recommendation import DEFAULT_RECOMMENDATION_LIMIT
from ..utils.errors import ForbiddenError, NotFoundError
from ..utils.time import utcnow
from .job_service import JobService
from .matching_service import (
    MODEL_VERSION_EMBEDDING,
    embed_text,
    score_candidate_against_jobs,
)

CANDIDATE = "candidate"


def profile_text(candidate: dict[str, Any]) -> str:
    """The text a candidate is represented by, in the same shape a CV would be.

    Prefers the parsed profile CV, since that is the text the per-application
    scorer sees when the candidate applies. Falls back to the typed headline and
    skills so a candidate who has never uploaded a CV still gets a ranking
    derived from what they have told us.
    """
    cv_text = (candidate.get("cvParsedText") or "").strip()
    if cv_text:
        return cv_text
    parts = [str(candidate.get("headline") or "")]
    parts.extend(str(skill) for skill in (candidate.get("skills") or []))
    return " ".join(part for part in parts if part).strip()


def is_fresh(computed_at: Optional[datetime], profile_updated_at: Optional[datetime]) -> bool:
    """Whether a cached ranking still reflects the candidate's current profile.

    A missing ``computedAt`` is never fresh. A missing ``profileUpdatedAt`` (a
    user document written before the stamp existed) is resolved to ``createdAt``
    by the caller; if neither stamp exists the cache is treated as stale, so a
    legacy candidate is recomputed once and then carries a real stamp.
    """
    if computed_at is None or profile_updated_at is None:
        return False
    return computed_at >= profile_updated_at


class RecommendationService:
    def __init__(
        self,
        jobs: JobRepository,
        users: UserRepository,
        recommendations: CandidateRecommendationRepository,
        job_service: JobService,
    ):
        self._jobs = jobs
        self._users = users
        self._recommendations = recommendations
        self._job_service = job_service

    def recommendations_for_candidate(
        self, candidate_id: str, limit: int = DEFAULT_RECOMMENDATION_LIMIT
    ) -> dict[str, Any]:
        """Return the candidate's ranking, computing it only if the cache is stale.

        This is the endpoint's whole decision: a cache document that is not older
        than the candidate's profile is authoritative and returned untouched, so
        a dashboard reload costs one Mongo read and no model inference.
        """
        candidate = self._require_candidate(candidate_id)
        cached = self._recommendations.find_by_candidate(candidate_id)
        if cached and is_fresh(
            cached.get("computedAt"),
            candidate.get("profileUpdatedAt") or candidate.get("createdAt"),
        ):
            rows = (cached.get("recommendations") or [])[:limit]
            return {"recommendations": rows, "computedAt": cached.get("computedAt")}

        return self.compute_candidate_recommendations(candidate_id, limit, candidate=candidate)

    def compute_candidate_recommendations(
        self,
        candidate_id: str,
        limit: int = DEFAULT_RECOMMENDATION_LIMIT,
        candidate: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Rank every open job for this candidate and refresh the cache.

        Writing the cache is part of computing, so a recompute is also the
        invalidation. ``candidate`` is accepted so the caller that already loaded
        the profile for its freshness check does not read it twice.
        """
        candidate = candidate or self._require_candidate(candidate_id)

        text = profile_text(candidate)
        jobs = self._jobs.find_open_with_embeddings()
        if not text or not jobs:
            # Cache the emptiness too, so a candidate with no profile does not
            # re-scan the open-job corpus on every dashboard load.
            return self._recommendations.upsert(candidate_id, [], utcnow())

        rows = score_candidate_against_jobs(
            text,
            jobs,
            profile_embedding=self._resolve_profile_embedding(candidate, text),
            limit=limit,
        )
        rows = self._attach_job_presentation(rows)
        return self._recommendations.upsert(candidate_id, rows, utcnow())

    def _resolve_profile_embedding(
        self, candidate: dict[str, Any], text: str
    ) -> Optional[list[float]]:
        """Re-use the candidate's stored vector, computing one only when needed.

        A stored vector is valid when the model that produced it is the one
        currently configured, so a model upgrade re-embeds every profile exactly
        once instead of leaving a mix of incompatible vector spaces behind. When
        the model cannot be loaded the scorer falls back to TF-IDF, so
        recommendations still work on an embedding-less host.
        """
        stored = self._users.find_profile_embedding(str(candidate["_id"])) or {}
        vector = stored.get("profileEmbedding")
        if vector and stored.get("profileEmbeddingModel") == MODEL_VERSION_EMBEDDING:
            return [float(value) for value in vector]

        try:
            vector = embed_text(text)
        except Exception:
            return None
        self._users.update(
            str(candidate["_id"]),
            {
                "profileEmbedding": vector,
                "profileEmbeddingModel": MODEL_VERSION_EMBEDDING,
            },
        )
        return vector

    def _attach_job_presentation(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Add the job title and company name each ranked row is displayed with.

        Only the rows that survived the limit are joined, and the join reuses
        ``JobService.enrich_with_employers`` — the public entry point that exists
        so this slice does not grow a second, divergent company lookup. Just the
        company name is kept on each row; the rest of the employer summary is not
        part of this response.
        """
        if not rows:
            return rows
        jobs = {
            str(job["_id"]): job
            for job in self._jobs.find_by_ids([row["jobId"] for row in rows])
        }
        self._job_service.enrich_with_employers(list(jobs.values()))
        for row in rows:
            job = jobs.get(row["jobId"])
            if not job:
                continue
            row["jobTitle"] = job.get("title") or ""
            row["companyName"] = (job.get("employer") or {}).get("companyName") or ""
        return rows

    def _require_candidate(self, candidate_id: str) -> dict[str, Any]:
        """Load the profile, enforcing the candidate role here as well as on the
        route so the rule holds for any caller of the service."""
        candidate = self._users.find_by_id(candidate_id)
        if not candidate:
            raise NotFoundError("User not found", code="user_not_found")
        if candidate.get("role") != CANDIDATE:
            raise ForbiddenError("Only candidate accounts have job recommendations")
        return candidate
