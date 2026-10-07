import re
from datetime import datetime

from bson import ObjectId

from ..repositories.application_repository import ApplicationRepository
from ..repositories.job_repository import JobRepository
from ..repositories.match_result_repository import MatchResultRepository
from ..repositories.user_repository import UserRepository
from ..schemas.user import COMPANY_SIZES
from ..utils.errors import ForbiddenError, NotFoundError
from ..utils.time import utcnow
from .employer_summary import build_employer_summary
from .matching_service import MODEL_VERSION_EMBEDDING, job_embedding

ROLE_EMPLOYER = "employer"

# The three fields ``_job_text`` folds into a job's embedding. An edit to any of
# them makes the stored vector wrong, and an edit to anything else (salary,
# status, location) leaves it correct — which is what keeps the recommender's
# re-embedding rare.
EMBEDDED_FIELDS = ("title", "description", "requiredSkills")

STAGE_TO_KEY = {
    "submitted": "submitted",
    "under_review": "underReview",
    "shortlisted": "shortlisted",
    "rejected": "rejected",
    "withdrawn": "withdrawn",
}


def is_expired(job: dict, now: datetime | None = None) -> bool:
    """Whether a posting's application deadline has already passed.

    A deadline is a *date*, stored at the end of the day it names
    (``utils.time.end_of_day``), so the test is one comparison against the shared
    naive-UTC clock and a posting stays open for the whole day it names. A posting
    with no deadline never expires on its own — the employer closes it themselves,
    which is why the field is optional.

    Expiry is *derived*, never written: no read mutates a document and there is
    no scheduler, so a role closes the instant its date passes rather than
    whenever a job happens to be swept. ``make db-expire-jobs`` exists only to
    converge the stored ``status`` field afterwards; this predicate is what
    actually enforces it.

    This is the business rule.
    ``repositories.job_repository.not_expired_clause`` is the same rule as a
    Mongo query for the set reads (browse, the recommender corpus). The two must
    not drift; ``test_job_expiry`` asserts they agree rather than leaving that to
    review.
    """
    deadline = job.get("deadline")
    return deadline is not None and deadline < (now or utcnow())


class JobService:
    """Job lifecycle plus the read-time joins the job views need.

    Four repositories are injected, one per collection the job views touch:
    ``jobs`` (the aggregate itself), ``users`` (to resolve the company behind a
    posting — a candidate must be able to see who they are applying to),
    ``applications`` (applicant counts and the per-stage funnel), and
    ``match_results`` (to invalidate scores when the required skills change).
    Each is used for exactly one reason and none is queried from a route.

    A posting also carries the embedding the candidate recommender searches by.
    It is written with the posting and refreshed only when one of the fields in
    ``EMBEDDED_FIELDS`` actually changes, so the common employer save costs no
    model call.
    """

    def __init__(
        self,
        jobs: JobRepository,
        users: UserRepository,
        applications: ApplicationRepository,
        match_results: MatchResultRepository,
    ):
        self._jobs = jobs
        self._users = users
        self._applications = applications
        self._match_results = match_results

    def create_job(self, employer_id: str, data: dict) -> dict:
        job = {
            **data,
            "employerId": ObjectId(employer_id),
            "status": "open",
            "createdAt": utcnow(),
            "updatedAt": utcnow(),
        }
        job.update(_embedding_fields(job))
        job_id = self._jobs.create(job)
        job["_id"] = ObjectId(job_id)
        job["applicantCount"] = 0
        self._attach_employers([job])
        return job

    def list_employer_jobs(self, employer_id: str) -> list[dict]:
        jobs = self._jobs.find_by_employer(employer_id)
        self._attach_applicant_counts(jobs)
        return jobs

    def list_open_jobs(self, filters: dict) -> tuple[list[dict], int]:
        """Public browse: one page of open jobs plus the total match count."""
        page = filters.get("page", 1)
        page_size = filters.get("pageSize", 12)
        jobs, total = self._jobs.page_open(
            self._build_browse_query(filters), filters.get("sort", "newest"), page, page_size
        )
        self._attach_applicant_counts(jobs)
        self._attach_employers(jobs)
        return jobs, total

    def get_job(self, job_id: str, viewer_id: str, viewer_role: str) -> dict:
        job = self._jobs.find_by_id(job_id)
        if not job:
            raise NotFoundError("Job not found", code="job_not_found")
        if viewer_role == ROLE_EMPLOYER:
            if str(job["employerId"]) != viewer_id:
                raise ForbiddenError("You do not have access to this job")
        elif job["status"] != "open" or is_expired(job):
            raise NotFoundError("Job not found", code="job_not_found")
        self._attach_applicant_counts([job])
        self._attach_employers([job])
        return job

    def update_job(self, job_id: str, employer_id: str, data: dict) -> dict:
        job = self._jobs.find_by_id(job_id)
        if not job:
            raise NotFoundError("Job not found", code="job_not_found")
        if str(job["employerId"]) != employer_id:
            raise ForbiddenError("You do not have permission to edit this job")

        updates = {**data, "updatedAt": utcnow()}
        if _embedding_is_stale(job, data):
            # Embedded against the merged document so the vector reflects the
            # edit in the same write that stores it.
            updates.update(_embedding_fields({**job, **data}))
        updated = self._jobs.update(job_id, updates)
        if "requiredSkills" in data and data["requiredSkills"] != (job.get("requiredSkills") or []):
            self._invalidate_matches(job_id)
        self._attach_applicant_counts([updated])
        self._attach_employers([updated])
        return updated

    def enrich_with_employers(self, jobs: list[dict]) -> list[dict]:
        """Attach the public company summary to already-loaded job documents.

        Public so the profile slice can present a candidate's saved jobs with
        the same company block the browse list shows, instead of a second,
        divergent copy of that join.
        """
        self._attach_employers(jobs)
        return jobs

    def funnel_for_job(self, job_id: str, employer_id: str) -> dict:
        job = self._jobs.find_by_id(job_id)
        if not job:
            raise NotFoundError("Job not found", code="job_not_found")
        if str(job["employerId"]) != employer_id:
            raise ForbiddenError("You do not have access to this job")
        return self._funnel([job])[0]

    def funnel_for_employer(self, employer_id: str) -> list[dict]:
        jobs = self._jobs.find_by_employer(employer_id)
        return self._funnel(jobs)

    def employer_overview(self, employer_id: str) -> dict:
        """Headline counters for the employer dashboard."""
        jobs = self._jobs.find_by_employer(employer_id)
        job_ids = [str(job["_id"]) for job in jobs]
        stages = self._applications.funnel_by_job(job_ids)
        # Count *effectively* open jobs, not stored ones: a dashboard that claims
        # 3 open roles while browse shows 2 would be counting a deadline the
        # candidate can already see has passed.
        open_jobs = sum(
            1 for job in jobs if job["status"] == "open" and not is_expired(job)
        )
        closed_jobs = len(jobs) - open_jobs
        total = sum(sum(counts.values()) for counts in stages.values())
        shortlisted = sum(counts.get("shortlisted", 0) for counts in stages.values())
        return {
            "openJobs": open_jobs,
            "closedJobs": closed_jobs,
            "totalApplicants": total,
            "shortlisted": shortlisted,
            "averageScore": self._applications.average_score(job_ids),
        }

    def _build_browse_query(self, filters: dict) -> dict:
        """Translate validated browse filters into a Mongo query.

        ``salaryMin`` matches jobs whose *top* of the band reaches the requested
        floor, so filtering for "at least 60k" returns the 55-75k role. Skill
        filters are conjunctive: selecting React and Docker returns roles that
        ask for both.

        The text search goes under ``$and`` because the repository owns the
        top-level ``$or`` that excludes expired postings. A second top-level
        ``$or`` here would replace that one and silently drop expiry from browse.
        """
        query: dict = {}
        if filters.get("q"):
            pattern = re.compile(re.escape(filters["q"]), re.IGNORECASE)
            query["$and"] = [{"$or": [{"title": pattern}, {"description": pattern}]}]
        if filters.get("location"):
            query["location"] = re.compile(re.escape(filters["location"]), re.IGNORECASE)
        if filters.get("employmentType"):
            query["employmentType"] = filters["employmentType"]
        if filters.get("experienceLevel"):
            query["experienceLevel"] = filters["experienceLevel"]
        if filters.get("remote") is not None:
            query["remote"] = filters["remote"]
        if filters.get("salaryMin") is not None:
            query["salaryMax"] = {"$gte": filters["salaryMin"]}
        if filters.get("skills"):
            query["requiredSkills"] = {"$all": filters["skills"]}
        return query

    def _attach_employers(self, jobs: list[dict]) -> None:
        employers = {
            str(user["_id"]): user
            for user in self._users.find_by_ids([str(job["employerId"]) for job in jobs])
        }
        for job in jobs:
            employer = employers.get(str(job["employerId"]))
            if employer:
                job["employer"] = build_employer_summary(employer)

    def _attach_applicant_counts(self, jobs: list[dict]) -> None:
        counts = self._applications.counts_by_job([str(job["_id"]) for job in jobs])
        for job in jobs:
            job["applicantCount"] = counts.get(str(job["_id"]), 0)

    def _funnel(self, jobs: list[dict]) -> list[dict]:
        stages = self._applications.funnel_by_job([str(job["_id"]) for job in jobs])
        return [
            {
                "jobId": str(job["_id"]),
                "title": job["title"],
                "status": job["status"],
                "stages": _empty_stages(stages.get(str(job["_id"]), {})),
            }
            for job in jobs
        ]

    def _invalidate_matches(self, job_id: str) -> None:
        """Reset stored scores after a required-skills change (see the
        repository method for why the rows are reset rather than deleted)."""
        applications = self._applications.find_by_job(job_id)
        self._match_results.reset_to_pending([str(app["_id"]) for app in applications])


def _embedding_is_stale(job: dict, data: dict) -> bool:
    """Whether an edit changes the text a job's stored vector was built from.

    A same-value resubmit is not stale: re-encoding on every save would make an
    employer fix a typo pay for a model call for no change in meaning.
    """
    return any(field in data and data[field] != job.get(field) for field in EMBEDDED_FIELDS)


def _embedding_fields(job: dict) -> dict:
    """The stored-vector fields for a job document.

    A posting is never rejected because its vector could not be computed: the
    recommender falls back to TF-IDF for jobs without one, so the cost of an
    embedding-less host is a weaker ranking rather than a failed job post.

    Both fields are always written together, as an explicit null when the encode
    fails. Returning nothing instead would leave the *previous* vector attached to
    a posting whose text has changed — a vector describing a job that no longer
    exists, which then scores as if it were current instead of taking the weaker
    TF-IDF path it should fall back to.
    """
    vector = job_embedding(job)
    if vector is None:
        return {"embedding": None, "embeddingModel": None}
    return {"embedding": vector, "embeddingModel": MODEL_VERSION_EMBEDDING}


def _empty_stages(counts: dict[str, int]) -> dict:
    stages = {key: counts.get(status, 0) for status, key in STAGE_TO_KEY.items()}
    stages["total"] = sum(counts.values())
    return stages


__all__ = [
    "COMPANY_SIZES",
    "EMBEDDED_FIELDS",
    "JobService",
    "ROLE_EMPLOYER",
    "STAGE_TO_KEY",
    "is_expired",
]
