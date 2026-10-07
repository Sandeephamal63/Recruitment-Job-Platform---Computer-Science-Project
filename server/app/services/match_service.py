"""Match orchestration: score an application and persist the result.

``matching_service.score_cv`` stays pure (text in, score out); this service
glues it to the ``matchResults`` collection and wraps access-control rules that
mirror the applications slice (candidate owns the application, employer owns
the job). Results are materialised lazily on first read, upgrading the M3
``pending`` placeholders in place.
"""

from bson import ObjectId

from ..repositories.application_repository import ApplicationRepository
from ..repositories.job_repository import JobRepository
from ..repositories.match_result_repository import MatchResultRepository
from ..repositories.user_repository import UserRepository
from ..utils.errors import ForbiddenError, NotFoundError
from . import matching_service

ROLE_EMPLOYER = "employer"


def serialize_match(result: dict) -> dict:
    """Wire shape of a stored match result (shared with ApplicationService)."""
    created_at = result.get("createdAt")
    return {
        "applicationId": str(result["applicationId"]),
        "matchScore": result.get("matchScore"),
        "matchedSkills": result.get("matchedSkills") or [],
        "missingSkills": result.get("missingSkills") or [],
        "recommendations": result.get("recommendations") or [],
        "modelVersion": result.get("modelVersion"),
        "createdAt": created_at.isoformat() + "Z" if created_at else None,
    }


class MatchService:
    def __init__(
        self,
        applications: ApplicationRepository,
        jobs: JobRepository,
        match_results: MatchResultRepository,
        users: UserRepository | None = None,
    ):
        self._applications = applications
        self._jobs = jobs
        self._match_results = match_results
        self._users = users

    def get_or_run(self, application_id: str, viewer_id: str, viewer_role: str) -> dict:
        """Return the stored result, computing (and persisting) it if pending."""
        application = self._authorize(application_id, viewer_id, viewer_role)
        result = self._match_results.find_by_application(application_id)
        if result and result.get("modelVersion") != "pending":
            return self._serialize(result)
        return self._compute_and_persist(application)

    def list_for_candidate(self, candidate_id: str) -> list[dict]:
        """All of a candidate's match results, computing the pending ones."""
        applications = self._applications.find_by_candidate(candidate_id)
        results: list[dict] = []
        for application in applications:
            application_id = str(application["_id"])
            stored = self._match_results.find_by_application(application_id)
            if stored and stored.get("modelVersion") != "pending":
                results.append(self._serialize(stored))
                continue
            results.append(self._compute_and_persist(application))
        return results

    def _compute_and_persist(self, application: dict) -> dict:
        application_id = str(application["_id"])
        computed = {**self._score_application(application), "applicationId": ObjectId(application_id)}
        self._match_results.upsert_result(application_id, computed)
        return self._serialize(computed)

    def _score_application(self, application: dict) -> dict:
        job = self._jobs.find_by_id(str(application["jobId"]))
        if not job:
            raise NotFoundError("Job not found", code="job_not_found")
        return matching_service.score_cv(application.get("cvParsedText") or "", job)

    def preview(self, job_id: str, candidate_id: str) -> dict:
        """Score a candidate's profile CV against a job without creating an application."""
        user = self._users.find_by_id(candidate_id) if self._users else None
        if not user:
            raise NotFoundError("User not found", code="user_not_found")
        job = self._jobs.find_by_id(job_id)
        if not job:
            raise NotFoundError("Job not found", code="job_not_found")
        cv_text = user.get("cvParsedText") or ""
        result = matching_service.score_cv(cv_text, job)
        return {
            "matchScore": result.get("matchScore"),
            "matchedSkills": result.get("matchedSkills") or [],
            "missingSkills": result.get("missingSkills") or [],
            "recommendations": result.get("recommendations") or [],
            "modelVersion": result.get("modelVersion"),
        }

    def _serialize(self, result: dict) -> dict:
        return serialize_match(result)

    def _authorize(self, application_id: str, viewer_id: str, viewer_role: str) -> dict:
        application = self._applications.find_by_id(application_id)
        if not application:
            raise NotFoundError("Application not found", code="application_not_found")
        if viewer_role == ROLE_EMPLOYER:
            job = self._jobs.find_by_id(str(application["jobId"]))
            if not job or str(job["employerId"]) != viewer_id:
                raise ForbiddenError("You do not have access to this application")
        elif str(application["candidateId"]) != viewer_id:
            raise ForbiddenError("You do not have access to this application")
        return application