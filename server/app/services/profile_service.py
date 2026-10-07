"""Candidate and employer profile management.

Owns the *self-service* surface over the ``users`` collection: the fields a
candidate fills in (headline, skills, a reusable profile CV) and the fields an
employer fills in (company description, industry, size). Session identity stays
in :mod:`app.services.auth_service` — this service is the profile domain, not
the login domain, and the two share only the ``UserRepository``.

The profile CV is stored in GridFS exactly like an application CV (same
repository, same validation) and the skills the gazetteer finds in it are
written back to ``users.skills``, so a candidate never has to retype what their
own CV already says. ``cvParsedText`` is used to seed skills and then discarded
from the response; it stays on the user document for reuse at apply time.

The candidate avatar is the mirror of the employer logo: an image stored in
GridFS, replaced atomically, and served to a second audience. It is *not*
served the way a logo is. A logo is public because an ``<img>`` tag cannot send
a bearer token, but an avatar is only ever read by an authenticated viewer, so
its own read is ``jwt_required`` and the employer-side read is gated on
ownership of the application it would be attached to — the same rule the
applicant endpoints already use.
"""

from bson import ObjectId

from ..repositories.application_repository import ApplicationRepository
from ..repositories.avatar_repository import AvatarRepository
from ..repositories.cv_repository import CVRepository
from ..repositories.job_repository import JobRepository
from ..repositories.logo_repository import LogoRepository
from ..repositories.user_repository import UserRepository
from ..utils.errors import ConflictError, ForbiddenError, NotFoundError
from ..utils.time import utcnow
from ..utils.urls import company_logo_url_for
from .avatar_service import validate_avatar
from .cv_service import validate_and_parse
from .logo_service import validate_logo
from .skills_gazetteer import extract_skills

CANDIDATE = "candidate"
EMPLOYER = "employer"

# A bookmark list long enough to be a spam/abuse vector, short enough to embed in
# the user document — which is why saved jobs are ids on the user rather than a
# sixth collection: an inherently user-owned, never-queried-against list.
MAX_SAVED_JOBS = 200

# Skills are back-filled from the CV, so a long CV can produce a long list. The
# cap matches the job's requiredSkills cap so both sides stay comparable.
MAX_PROFILE_SKILLS = 40

# The profile fields a candidate is represented by: the text the recommender
# embeds and ranks. An edit to any of them invalidates the cached ranking and
# vector (see ``_profile_stamp``).
#
# Deliberately broader than the scorer's own preference order, which uses the CV
# when there is one and falls back to headline + skills otherwise. This service
# cannot know which the candidate currently has — that depends on whether they
# uploaded a CV — so it stamps the union instead of trying to mirror a rule that
# lives in another slice. Over-invalidating costs one short re-encode and a
# recomputed ranking; under-invalidating would rank the candidate on stale text.
PROFILE_TEXT_FIELDS = frozenset({"cvParsedText", "headline", "skills"})


def _profile_stamp() -> dict:
    """Move ``profileUpdatedAt`` and drop the profile vector that is now stale.

    Both halves describe one event: the text this candidate is represented by has
    changed, so the cached ranking (``candidateRecommendations``) *and* the cached
    vector (``users.profileEmbedding``) are both describing the text they were
    built from. Invalidating only the ranking would leave the recommender
    recomputing — as the whole point of the recompute is to see the new text —
    against the previous CV's vector.

    Unsetting the vector is the same trade-off ``JobService`` makes on a posting
    edit: recompute lazily and let the recommender rebuild it on the next read.
    Redundant invalidation costs one short encode; a stale vector would rank a
    candidate on a CV they no longer have, with no signal that it had happened.
    """
    return {
        "profileUpdatedAt": utcnow(),
        "profileEmbedding": None,
        "profileEmbeddingModel": None,
    }


def _changes_represented_text(data: dict) -> bool:
    """Whether an update touches the text this candidate is represented by."""
    return not PROFILE_TEXT_FIELDS.isdisjoint(data)


class ProfileService:
    def __init__(
        self,
        users: UserRepository,
        cvs: CVRepository,
        jobs: JobRepository,
        logos: LogoRepository,
        applications: ApplicationRepository,
        avatars: AvatarRepository,
    ):
        self._users = users
        self._cvs = cvs
        self._jobs = jobs
        self._logos = logos
        self._applications = applications
        self._avatars = avatars

    def get_profile(self, user_id: str) -> dict:
        return self._require_user(user_id)

    def update_profile(self, user_id: str, data: dict) -> dict:
        self._require_user(user_id)
        if not data:
            return self._require_user(user_id)
        updates = {**data, "updatedAt": utcnow()}
        if _changes_represented_text(data):
            updates.update(_profile_stamp())
        return self._users.update(user_id, updates)

    def upload_cv(self, user_id: str, file_storage) -> dict:
        """Store a reusable profile CV and back-fill the candidate's skills.

        The previous profile CV is deleted only after the new one is written, so
        a failed upload leaves the candidate with the CV they already had.
        """
        user = self._require_user(user_id)
        if user["role"] != CANDIDATE:
            raise ConflictError(
                "Only candidate accounts store a profile CV", code="profile_cv_not_supported"
            )

        cv_bytes, cv_text = validate_and_parse(file_storage)
        new_ref = self._cvs.save(cv_bytes, file_storage.filename or "cv")
        previous_ref = user.get("cvFileRef")

        extracted = sorted(extract_skills(cv_text))[:MAX_PROFILE_SKILLS]
        updates = {
            "cvFileRef": new_ref,
            "cvFileName": file_storage.filename or "cv",
            "cvParsedText": cv_text,
            "updatedAt": utcnow(),
            **_profile_stamp(),
        }
        if extracted:
            updates["skills"] = extracted

        updated = self._users.update(user_id, updates)
        if previous_ref:
            self._cvs.delete(previous_ref)
        return {
            "cvFileName": updates["cvFileName"],
            "extractedSkills": extracted if extracted else (user.get("skills") or []),
            "characterCount": len(cv_text),
        }

    def download_cv(self, user_id: str) -> tuple[bytes, str]:
        user = self._require_user(user_id)
        if not user.get("cvFileRef"):
            raise NotFoundError("No profile CV has been uploaded", code="profile_cv_missing")
        return self._cvs.load(user["cvFileRef"])

    def delete_cv(self, user_id: str) -> dict:
        user = self._require_user(user_id)
        if user.get("cvFileRef"):
            self._cvs.delete(user["cvFileRef"])
        return self._users.update(
            user_id,
            {
                "cvFileRef": None,
                "cvFileName": None,
                "cvParsedText": None,
                "updatedAt": utcnow(),
                **_profile_stamp(),
            },
        )

    def upload_company_logo(self, user_id: str, file_storage) -> dict:
        """Store an employer's company logo and return its public URL.

        The previous logo is deleted only after the new one is written, so a
        failed upload leaves the employer with the logo they already had.
        """
        user = self._require_employer(user_id)
        logo_bytes = validate_logo(file_storage)
        filename = file_storage.filename or "logo"
        new_ref = self._logos.save(logo_bytes, filename)
        previous_ref = user.get("logoFileRef")

        updated = self._users.update(
            user_id, {"logoFileRef": new_ref, "logoFileName": filename, "updatedAt": utcnow()}
        )
        if previous_ref:
            self._logos.delete(previous_ref)
        return {
            "companyLogoUrl": company_logo_url_for(updated, str(user_id)),
            "companyLogoFileName": filename,
        }

    def download_company_logo(self, employer_id: str) -> tuple[bytes, str]:
        """Public, unauthenticated read of an employer's logo bytes.

        The landing page renders the employer strip for anonymous visitors, so
        this is intentionally not owner-gated. It exposes the image and nothing
        else — no profile fields, no contact details.
        """
        user = self._require_user(employer_id)
        if not user.get("logoFileRef"):
            raise NotFoundError("This company has not uploaded a logo", code="company_logo_missing")
        return self._logos.load(user["logoFileRef"])

    def delete_company_logo(self, user_id: str) -> dict:
        self._require_employer(user_id)
        user = self._require_user(user_id)
        if user.get("logoFileRef"):
            self._logos.delete(user["logoFileRef"])
        return self._users.update(
            user_id, {"logoFileRef": None, "logoFileName": None, "updatedAt": utcnow()}
        )

    def upload_avatar(self, user_id: str, file_storage) -> dict:
        """Store a candidate's profile avatar.

        The previous avatar is deleted only after the new one is written, so a
        failed upload leaves the candidate with the avatar they already had.

        Deliberately does *not* stamp the profile: an avatar is not text, so
        replacing one must not invalidate the candidate's cached ranking or
        vector (see ``_profile_stamp``).
        """
        user = self._require_candidate(user_id)
        avatar_bytes = validate_avatar(file_storage)
        filename = file_storage.filename or "avatar"
        new_ref = self._avatars.save(avatar_bytes, filename)
        previous_ref = user.get("avatarFileRef")

        self._users.update(
            user_id, {"avatarFileRef": new_ref, "avatarFileName": filename, "updatedAt": utcnow()}
        )
        if previous_ref:
            self._avatars.delete(previous_ref)
        return {"avatarFileName": filename}

    def download_avatar(self, user_id: str) -> tuple[bytes, str]:
        user = self._require_candidate(user_id)
        if not user.get("avatarFileRef"):
            raise NotFoundError("No profile avatar has been uploaded", code="avatar_missing")
        return self._avatars.load(user["avatarFileRef"])

    def delete_avatar(self, user_id: str) -> dict:
        self._require_candidate(user_id)
        user = self._require_user(user_id)
        if user.get("avatarFileRef"):
            self._avatars.delete(user["avatarFileRef"])
        return self._users.update(
            user_id, {"avatarFileRef": None, "avatarFileName": None, "updatedAt": utcnow()}
        )

    def download_candidate_avatar(self, employer_id: str, application_id: str) -> tuple[bytes, str]:
        """An applicant's avatar, readable only by the employer who owns the job.

        Keyed on the application rather than the candidate id so the check is the
        one the applicant endpoints already make: an employer may see the people
        who applied to *their* postings, and no one else. Reading by candidate id
        alone would hand every employer every candidate's photo.
        """
        application = self._applications.find_by_id(application_id)
        if not application:
            raise NotFoundError("Application not found", code="application_not_found")
        job = self._jobs.find_by_id(str(application["jobId"]))
        if not job or str(job["employerId"]) != employer_id:
            raise ForbiddenError("You do not have access to this application")

        candidate = self._users.find_by_id(str(application["candidateId"]))
        if not candidate or not candidate.get("avatarFileRef"):
            raise NotFoundError("This candidate has not uploaded an avatar", code="avatar_missing")
        return self._avatars.load(candidate["avatarFileRef"])

    def list_saved_jobs(self, user_id: str) -> list[dict]:
        user = self._require_user(user_id)
        saved_ids = [str(job_id) for job_id in (user.get("savedJobIds") or [])]
        if not saved_ids:
            return []
        jobs = {str(job["_id"]): job for job in self._jobs.find_by_ids(saved_ids)}
        return [jobs[job_id] for job_id in saved_ids if job_id in jobs]

    def save_job(self, user_id: str, job_id: str) -> dict:
        user = self._require_user(user_id)
        job = self._jobs.find_by_id(job_id)
        if not job or job["status"] != "open":
            raise NotFoundError("Job not found", code="job_not_found")
        object_id = ObjectId(job_id)
        if object_id in (user.get("savedJobIds") or []):
            return user
        if len(user.get("savedJobIds") or []) >= MAX_SAVED_JOBS:
            raise ConflictError(
                f"You can save at most {MAX_SAVED_JOBS} jobs", code="saved_jobs_limit_reached"
            )
        return self._users.add_saved_job(user_id, object_id)

    def remove_saved_job(self, user_id: str, job_id: str) -> dict:
        self._require_user(user_id)
        try:
            object_id = ObjectId(job_id)
        except Exception:
            raise NotFoundError("Job not found", code="job_not_found")
        return self._users.remove_saved_job(user_id, object_id)

    def _require_user(self, user_id: str) -> dict:
        user = self._users.find_by_id(user_id)
        if not user:
            raise NotFoundError("User not found", code="user_not_found")
        return user

    def _require_employer(self, user_id: str) -> dict:
        """Logo writes are employer-only, enforced here rather than only on the
        route so the rule holds for any caller of the service."""
        user = self._require_user(user_id)
        if user["role"] != EMPLOYER:
            raise ConflictError(
                "Only employer accounts can store a company logo", code="company_logo_not_supported"
            )
        return user

    def _require_candidate(self, user_id: str) -> dict:
        """Avatar reads and writes are candidate-only, enforced here for the same
        reason as :meth:`_require_employer` — the route decorator is the first
        line of defence, not the only one."""
        user = self._require_user(user_id)
        if user["role"] != CANDIDATE:
            raise ConflictError(
                "Only candidate accounts can store a profile avatar", code="avatar_not_supported"
            )
        return user
