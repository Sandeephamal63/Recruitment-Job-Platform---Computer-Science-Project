from marshmallow import fields

from ..utils.urls import company_logo_url_for
from .base import BaseSchema
from .job import dump_deadline
from .user import COMPANY_SIZES, EMPLOYER, EmployerSummarySchema

employer_summary_schema = EmployerSummarySchema()


class ProfileSchema(BaseSchema):
    """Self-service view of the signed-in user's profile (dump side).

    Superset of :class:`UserSchema` for the owner only: it adds the company
    fields an employer fills in, the profile-CV presence flag the candidate CV
    library renders, the avatar filename, and the saved-job list.
    ``cvParsedText`` is never dumped.
    """

    id = fields.Function(lambda user: str(user["_id"]))
    role = fields.Str()
    name = fields.Str()
    email = fields.Str()
    headline = fields.Function(lambda user: (user or {}).get("headline") or "")
    skills = fields.Function(lambda user: (user or {}).get("skills") or [])
    companyName = fields.Function(lambda user: (user or {}).get("companyName") or "")
    companyDescription = fields.Function(lambda user: (user or {}).get("companyDescription") or "")
    companyIndustry = fields.Function(lambda user: (user or {}).get("companyIndustry") or "")
    companySize = fields.Function(lambda user: (user or {}).get("companySize") or "")
    companyLogoUrl = fields.Function(
        lambda user: company_logo_url_for(user or {}, str(user["_id"]))
    )
    companyLogoFileName = fields.Function(lambda user: (user or {}).get("logoFileName") or "")
    hasProfileCv = fields.Function(lambda user: bool((user or {}).get("cvFileRef")))
    cvFileName = fields.Function(lambda user: (user or {}).get("cvFileName"))
    avatarFileName = fields.Function(lambda user: (user or {}).get("avatarFileName"))
    savedJobIds = fields.Function(lambda user: [str(job_id) for job_id in (user or {}).get("savedJobIds") or []])
    createdAt = fields.Function(lambda user: user["createdAt"].isoformat() + "Z")
    updatedAt = fields.Function(lambda user: user.get("updatedAt").isoformat() + "Z" if user.get("updatedAt") else None)


class SavedJobSchema(BaseSchema):
    """A bookmarked job, rehydrated from the ``jobs`` collection at read time.

    The commercial fields (``salaryMin``/``salaryMax``/``currency``,
    ``experienceLevel``, ``remote``) were absent here while the client's
    ``SavedJob`` type declared all of them as present, so the saved-jobs list
    rendered ``undefined`` for each. They are dumped now, with the same
    ``.get(...) or`` defaults ``JobSchema`` uses so a posting that predates a
    field still serializes a usable value instead of dropping the key.
    """

    id = fields.Function(lambda job: str(job["_id"]))
    title = fields.Str()
    location = fields.Str()
    employmentType = fields.Str()
    requiredSkills = fields.Function(lambda job: job.get("requiredSkills") or [])
    status = fields.Str()
    deadline = fields.Function(dump_deadline)
    salaryMin = fields.Function(lambda job: job.get("salaryMin"))
    salaryMax = fields.Function(lambda job: job.get("salaryMax"))
    currency = fields.Function(lambda job: job.get("currency") or "GBP")
    experienceLevel = fields.Function(lambda job: job.get("experienceLevel") or "")
    remote = fields.Function(lambda job: job.get("remote"))
    createdAt = fields.Function(lambda job: job["createdAt"].isoformat() + "Z")
    employer = fields.Function(lambda job: job.get("employer"))


class ProfileCvSchema(BaseSchema):
    """Response for a profile-CV upload: which file is stored and what the
    pipeline extracted from it, so the profile page can confirm the parse."""

    cvFileName = fields.Str()
    extractedSkills = fields.List(fields.Str())
    characterCount = fields.Integer()


class ProfileLogoSchema(BaseSchema):
    """Response for a company-logo upload: the public URL to render and the
    stored filename, so the profile page can confirm the upload."""

    companyLogoUrl = fields.Str()
    companyLogoFileName = fields.Str()


class ProfileAvatarSchema(BaseSchema):
    """Response for an avatar upload: the stored filename.

    No URL, unlike a company logo. A logo is served from a public route so an
    ``<img>`` can load it; an avatar is only ever read by an authenticated
    caller, so the client fetches it through the API and there is no
    fetchable-from-``src`` address to hand out here.
    """

    avatarFileName = fields.Str()


profile_schema = ProfileSchema()
saved_job_schema = SavedJobSchema()
profile_cv_schema = ProfileCvSchema()
profile_logo_schema = ProfileLogoSchema()
profile_avatar_schema = ProfileAvatarSchema()

__all__ = [
    "COMPANY_SIZES",
    "EMPLOYER",
    "ProfileAvatarSchema",
    "ProfileSchema",
    "SavedJobSchema",
    "profile_avatar_schema",
    "profile_cv_schema",
    "profile_logo_schema",
    "profile_schema",
    "saved_job_schema",
]
