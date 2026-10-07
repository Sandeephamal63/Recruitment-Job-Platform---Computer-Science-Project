from bson import ObjectId
from pymongo.database import Database

from ..repositories.application_repository import (
    PENDING_BAND_LABEL,
    SCORE_BAND_LABELS,
    ApplicationRepository,
)
from ..repositories.cv_repository import CVRepository
from ..repositories.job_repository import JobRepository
from ..repositories.match_result_repository import MatchResultRepository
from ..repositories.user_repository import UserRepository
from ..utils.errors import ConflictError, ForbiddenError, NotFoundError
from ..utils.time import utcnow
from .cv_service import upload_from_bytes, validate_and_parse
from .employer_summary import build_employer_summary
from .job_service import is_expired
from .match_service import serialize_match
from . import matching_service

ROLE_EMPLOYER = "employer"
ROLE_CANDIDATE = "candidate"

# Employer-driven funnel: progress forward only; rejected is terminal. Same-status
# PATCHes are idempotent no-ops; anything else outside the map is a conflict.
# ``withdrawn`` is candidate-owned — an employer can neither enter nor leave it.
STATUS_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"under_review", "shortlisted", "rejected"},
    "under_review": {"shortlisted", "rejected"},
    "shortlisted": {"rejected"},
    "rejected": set(),
    "withdrawn": set(),
}

# A candidate may withdraw at any point before a decision is final, including
# after being shortlisted; the recruiter's own record of the funnel is not
# something a withdrawal should erase.
CANDIDATE_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"withdrawn"},
    "under_review": {"withdrawn"},
    "shortlisted": {"withdrawn"},
    "rejected": set(),
    "withdrawn": set(),
}

CANDIDATE_PROFILE_FIELDS = ("name", "headline", "email", "skills")
MAX_NOTES = 50


class ApplicationService:
    def __init__(
        self,
        applications: ApplicationRepository,
        jobs: JobRepository,
        cvs: CVRepository,
        match_results: MatchResultRepository,
        users: UserRepository,
        db: Database,
    ):
        self._applications = applications
        self._jobs = jobs
        self._cvs = cvs
        self._match_results = match_results
        self._users = users
        self._db = db

    def apply(
        self,
        job_id: str,
        candidate_id: str,
        file_storage=None,
        use_profile_cv: bool = False,
    ) -> dict:
        job = self._jobs.find_by_id(job_id)
        if not job:
            raise NotFoundError("Job not found", code="job_not_found")
        # An expired deadline closes the role the same way an employer closing it
        # does, and the candidate is told the same thing: a posting that is no
        # longer accepting applications is closed, and *why* it closed is not
        # something a stranger browsing a listing needs to know.
        if job["status"] != "open" or is_expired(job):
            raise ConflictError("This job is no longer open", code="job_closed")
        if self._applications.find_duplicate(job_id, candidate_id):
            raise ConflictError("You have already applied to this job", code="already_applied")

        upload = self._resolve_cv_upload(candidate_id, file_storage, use_profile_cv)
        cv_bytes, cv_text = validate_and_parse(upload)
        cv_file_ref = self._cvs.save(cv_bytes, upload.filename or "cv")

        now = utcnow()
        application = {
            "jobId": ObjectId(job_id),
            "candidateId": ObjectId(candidate_id),
            "cvFileRef": cv_file_ref,
            "cvParsedText": cv_text,
            "status": "submitted",
            "notes": [],
            "submittedAt": now,
            "createdAt": now,
            "updatedAt": now,
        }

        try:
            with self._db.client.start_session() as session:
                with session.start_transaction():
                    application_id = self._applications.create(application, session=session)
                    self._match_results.create_placeholder(
                        ObjectId(application_id), now, session=session
                    )
        except Exception:
            self._cvs.delete(cv_file_ref)
            raise

        application["_id"] = ObjectId(application_id)
        application["job"] = self._job_preview(job)
        application["cvFileName"] = upload.filename
        return application

    def list_candidate_applications(self, candidate_id: str) -> list[dict]:
        """A candidate's own applications, with the score inline on each row.

        The score is the reason the candidate applied through this platform, so
        it travels with the row rather than forcing a second call per application.
        """
        applications = self._applications.find_by_candidate(candidate_id)
        self._attach_jobs(applications)
        self._attach_cv_filenames(applications)
        self._attach_matches(applications)
        self._attach_employers(applications)
        return applications

    def get_application(self, application_id: str, viewer_id: str, viewer_role: str) -> dict:
        application = self._authorize_read(application_id, viewer_id, viewer_role)
        self._attach_jobs([application])
        application = self._attach_cv_filenames([application])[0]
        self._attach_matches([application])
        if viewer_role == ROLE_EMPLOYER:
            self._attach_candidates([application])
            self._attach_employers([application])
        else:
            # The candidate is owed the company they applied to, so the summary
            # is joined for them too.
            self._attach_employers([application])
            # Review notes are the employer's private working notes — the notes
            # routes are employer-only, and that has to hold here as well or a
            # candidate reads them out of the application payload they own.
            application.pop("notes", None)
        return application

    def list_for_job(
        self,
        job_id: str,
        employer_id: str,
        status: str | None = None,
        min_score: int | None = None,
        sort: str = "newest",
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[dict], int]:
        """One page of a job's applicants, filtered/sorted in the database."""
        job = self._require_owned_job(job_id, employer_id)
        applications, total = self._applications.page_for_job(
            job_id, status, min_score, sort, page, page_size
        )
        self._attach_jobs(applications)
        self._attach_cv_filenames(applications)
        self._attach_candidates(applications)
        self._serialize_joined_matches(applications)
        return applications, total

    def counts_for_employer(self, employer_id: str) -> list[dict]:
        jobs = self._jobs.find_by_employer(employer_id)
        counts = self._applications.counts_by_job([str(job["_id"]) for job in jobs])
        return [{"jobId": str(job["_id"]), "count": counts.get(str(job["_id"]), 0)} for job in jobs]

    def score_distribution(self, job_id: str, employer_id: str) -> dict:
        self._require_owned_job(job_id, employer_id)
        return self._build_distribution(self._applications.score_distribution([job_id]))

    def employer_score_distribution(self, employer_id: str) -> dict:
        job_ids = [str(job["_id"]) for job in self._jobs.find_by_employer(employer_id)]
        return self._build_distribution(self._applications.score_distribution(job_ids))

    def update_status(
        self,
        application_id: str,
        employer_id: str,
        status: str,
        rejection_reason: str | None = None,
    ) -> dict:
        application = self._transition(
            self._require_owned_application(application_id, employer_id),
            STATUS_TRANSITIONS,
            status,
            rejection_reason,
        )
        # An employer updates a row in the applicant grid, so the response must
        # carry the same joins that grid is rendering or the row blanks out.
        self._attach_candidates([application])
        self._attach_employers([application])
        self._attach_matches([application])
        return application

    def withdraw(self, application_id: str, candidate_id: str) -> dict:
        application = self._applications.find_by_id(application_id)
        if not application:
            raise NotFoundError("Application not found", code="application_not_found")
        if str(application["candidateId"]) != candidate_id:
            raise ForbiddenError("You do not have access to this application")
        withdrawn = self._transition(application, CANDIDATE_TRANSITIONS, "withdrawn", None)
        # The candidate's own application list renders the score, so a withdrawn
        # row must come back with the match result still attached.
        self._attach_matches([withdrawn])
        return withdrawn

    def bulk_update_status(
        self,
        application_ids: list[str],
        employer_id: str,
        status: str,
        rejection_reason: str | None = None,
    ) -> dict:
        """Move several applications through the funnel at once.

        Every id is authorized and every transition validated *before* anything
        is written: a bulk action that silently skipped the applications it could
        not move would leave a recruiter believing a whole shortlist had been
        actioned when only part of it had.
        """
        moved: list[dict] = []
        skipped: list[dict] = []
        for application_id in application_ids:
            try:
                application = self._require_owned_application(application_id, employer_id)
            except (NotFoundError, ForbiddenError):
                skipped.append({"id": application_id, "reason": "not_found"})
                continue
            current = application["status"]
            if current == status or status not in STATUS_TRANSITIONS.get(current, set()):
                skipped.append({"id": application_id, "reason": f"cannot move from '{current}'"})
                continue
            self._applications.update_status(
                application_id, status, utcnow(), rejection_reason
            )
            moved.append({"id": application_id, "previousStatus": current})

        if not moved:
            raise ConflictError(
                "None of the selected applications can move to that status",
                code="invalid_transition",
            )
        return {"updated": len(moved), "skipped": skipped, "moved": moved}

    def list_notes(self, application_id: str, employer_id: str) -> list[dict]:
        application = self._require_owned_application(application_id, employer_id)
        return list(application.get("notes") or [])

    def add_note(self, application_id: str, employer_id: str, body: str) -> list[dict]:
        application = self._require_owned_application(application_id, employer_id)
        if len(application.get("notes") or []) >= MAX_NOTES:
            raise ConflictError(
                f"An application can hold at most {MAX_NOTES} notes", code="notes_limit_reached"
            )
        author = self._users.find_by_id(employer_id) or {}
        note = {
            "id": ObjectId(),
            "body": body,
            "authorUserId": ObjectId(employer_id),
            "authorName": author.get("name") or "Unknown",
            "createdAt": utcnow(),
        }
        updated = self._applications.add_note(application_id, note)
        return list(updated.get("notes") or [])

    def remove_note(self, application_id: str, employer_id: str, note_id: str) -> dict:
        self._require_owned_application(application_id, employer_id)
        try:
            return self._applications.remove_note(application_id, note_id)
        except ValueError:
            raise NotFoundError("Note not found", code="note_not_found")

    def stream_cv(self, application_id: str, viewer_id: str, viewer_role: str) -> tuple[bytes, str]:
        application = self._authorize_read(application_id, viewer_id, viewer_role)
        return self._cvs.load(application["cvFileRef"])

    def _resolve_cv_upload(self, candidate_id: str, file_storage, use_profile_cv: bool):
        """Pick the CV source: a fresh upload, or the candidate's saved one."""
        if file_storage is not None and getattr(file_storage, "filename", ""):
            return file_storage
        if not use_profile_cv:
            raise ConflictError("A CV file is required", code="cv_required")
        user = self._users.find_by_id(candidate_id) or {}
        if not user.get("cvFileRef"):
            raise NotFoundError(
                "You have not uploaded a profile CV yet", code="profile_cv_missing"
            )
        content, filename = self._cvs.load(user["cvFileRef"])
        return upload_from_bytes(content, filename)

    def _transition(
        self,
        application: dict,
        transitions: dict[str, set[str]],
        status: str,
        rejection_reason: str | None,
    ) -> dict:
        application_id = str(application["_id"])
        current = application["status"]
        if current != status:
            if status not in transitions.get(current, set()):
                raise ConflictError(
                    f"Cannot move an application from '{current}' to '{status}'",
                    code="invalid_transition",
                )
            application = self._applications.update_status(
                application_id, status, utcnow(), rejection_reason
            )
        self._attach_jobs([application])
        return self._attach_cv_filenames([application])[0]

    def _require_owned_job(self, job_id: str, employer_id: str) -> dict:
        job = self._jobs.find_by_id(job_id)
        if not job:
            raise NotFoundError("Job not found", code="job_not_found")
        if str(job["employerId"]) != employer_id:
            raise ForbiddenError("You do not have access to this job's applicants")
        return job

    def _require_owned_application(self, application_id: str, employer_id: str) -> dict:
        application = self._applications.find_by_id(application_id)
        if not application:
            raise NotFoundError("Application not found", code="application_not_found")
        job = self._jobs.find_by_id(str(application["jobId"]))
        if not job or str(job["employerId"]) != employer_id:
            raise ForbiddenError("You do not have access to this application")
        return application

    def _attach_jobs(self, applications: list[dict]) -> None:
        jobs = {
            str(job["_id"]): job
            for job in self._jobs.find_by_ids([str(app["jobId"]) for app in applications])
        }
        for application in applications:
            job = jobs.get(str(application["jobId"]))
            if job:
                application["job"] = self._job_preview(job)

    def _attach_employers(self, applications: list[dict]) -> None:
        job_ids = [str(app["jobId"]) for app in applications]
        jobs = {str(job["_id"]): job for job in self._jobs.find_by_ids(job_ids)}
        employer_ids = [str(jobs[job_id]["employerId"]) for job_id in job_ids if job_id in jobs]
        employers = {str(user["_id"]): user for user in self._users.find_by_ids(employer_ids)}
        for application, job_id in zip(applications, job_ids):
            job = jobs.get(job_id)
            if not job:
                continue
            employer = employers.get(str(job["employerId"]))
            if employer:
                application["employerId"] = str(employer["_id"])
                application["employer"] = build_employer_summary(employer)

    def _attach_candidates(self, applications: list[dict]) -> None:
        users = {
            str(user["_id"]): user
            for user in self._users.find_by_ids([str(app["candidateId"]) for app in applications])
        }
        for application in applications:
            user = users.get(str(application["candidateId"]))
            if user:
                application["candidate"] = {
                    "id": str(user["_id"]),
                    **{field: user.get(field) for field in CANDIDATE_PROFILE_FIELDS},
                }

    def _attach_matches(self, applications: list[dict]) -> None:
        """Attach each application's match result, computing any pending ones.

        Computes out-of-line so a first employer view behaves like the candidate
        view: the expensive work happens once, the result is persisted, and every
        later read is a plain lookup.
        """
        application_ids = [str(app["_id"]) for app in applications]
        stored = self._match_results.find_by_application_ids(application_ids)
        jobs = {
            str(job["_id"]): job
            for job in self._jobs.find_by_ids([str(app["jobId"]) for app in applications])
        }
        for application in applications:
            application_id = str(application["_id"])
            result = stored.get(application_id)
            if result and result.get("modelVersion") != "pending":
                application["match"] = serialize_match(result)
                continue
            job = jobs.get(str(application["jobId"]))
            if not job:
                application["match"] = None
                continue
            computed = {
                **matching_service.score_cv(application.get("cvParsedText") or "", job),
                "applicationId": ObjectId(application_id),
            }
            self._match_results.upsert_result(application_id, computed)
            application["match"] = serialize_match(computed)

    def _serialize_joined_matches(self, applications: list[dict]) -> None:
        """Normalize the ``$lookup``-joined match documents from
        :meth:`ApplicationRepository.page_for_job` into the wire shape."""
        for application in applications:
            joined = application.pop("match", None)
            application["match"] = serialize_match(joined) if joined else None

    def _attach_cv_filenames(self, applications: list[dict]) -> list[dict]:
        names = self._cvs.filenames_by_ids([ObjectId(a["cvFileRef"]) for a in applications])
        for application in applications:
            application["cvFileName"] = names.get(str(application["cvFileRef"]))
        return applications

    def _build_distribution(self, raw_buckets: list[dict]) -> dict:
        """Normalize a ``$bucket`` result into an ordered, gap-free histogram."""
        by_band = {bucket["band"]: bucket["count"] for bucket in raw_buckets}
        buckets = [{"band": label, "count": by_band.get(label, 0)} for label in SCORE_BAND_LABELS]
        pending = by_band.get(PENDING_BAND_LABEL, 0)
        if pending:
            buckets.append({"band": PENDING_BAND_LABEL, "count": pending})
        return {"buckets": buckets, "total": sum(bucket["count"] for bucket in buckets)}

    def _job_preview(self, job: dict) -> dict:
        return {
            "id": str(job["_id"]),
            "title": job["title"],
            "description": job.get("description"),
            "status": job["status"],
            "location": job.get("location"),
            "employmentType": job.get("employmentType"),
            "requiredSkills": job.get("requiredSkills") or [],
        }

    def _authorize_read(self, application_id: str, viewer_id: str, viewer_role: str) -> dict:
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
