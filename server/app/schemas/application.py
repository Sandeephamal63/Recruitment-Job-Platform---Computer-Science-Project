from marshmallow import ValidationError, fields, validate, validates_schema

from .base import BaseSchema
from .match_result import MatchResultSchema
from .user import EmployerSummarySchema

APPLICATION_STATUSES = ("submitted", "under_review", "shortlisted", "rejected", "withdrawn")
REVIEW_STATUSES = ("under_review", "shortlisted", "rejected")
CANDIDATE_STATUSES = ("withdrawn",)

APPLICANT_SORTS = ("newest", "oldest", "score-desc", "score-asc")

MAX_NOTES = 50
MAX_NOTE_LEN = 2000
MAX_BULK_IDS = 100
MAX_REJECTION_REASON_LEN = 500

PAGE_SIZE_DEFAULT = 25
PAGE_SIZE_MAX = 100

employer_summary_schema = EmployerSummarySchema()


class CandidateProfileSchema(BaseSchema):
    """Employer-facing snapshot of an applicant's profile (joined at read time)."""

    id = fields.Str()
    name = fields.Str(allow_none=True)
    headline = fields.Str(allow_none=True)
    email = fields.Str(allow_none=True)
    skills = fields.List(fields.Str(), allow_none=True)


class NoteSchema(BaseSchema):
    """A review note attached to an application.

    ``authorName`` is an intentional snapshot of the name at the time of writing:
    a note is a record of a decision made by a specific person, so it must not
    silently re-attribute itself if that person later renames their account.

    The schema owns the ObjectId/datetime to wire conversion, so services return
    stored note documents as-is and no caller has to remember to stringify ids.
    """

    id = fields.Function(lambda note: str(note["id"]))
    body = fields.Str()
    authorUserId = fields.Function(lambda note: str(note["authorUserId"]))
    authorName = fields.Str()
    createdAt = fields.Function(lambda note: note["createdAt"].isoformat() + "Z")


note_schema = NoteSchema()


class ApplicationSchema(BaseSchema):
    """Wire shape of an application document (dump side).

    ``job``, ``candidate``, ``match``, ``employer`` and ``cvFileName`` are
    joined at read time by the service (AGENTS: never denormalize); the raw
    document never carries them.
    """

    id = fields.Function(lambda app: str(app["_id"]))
    jobId = fields.Function(lambda app: str(app["jobId"]))
    candidateId = fields.Function(lambda app: str(app["candidateId"]))
    employerId = fields.Function(lambda app: app.get("employerId"))
    status = fields.Str()
    rejectionReason = fields.Function(lambda app: app.get("rejectionReason"))
    notes = fields.Function(
        lambda app: [note_schema.dump(note) for note in (app.get("notes") or [])]
    )
    submittedAt = fields.Function(lambda app: app["submittedAt"].isoformat() + "Z")
    updatedAt = fields.Function(lambda app: app["updatedAt"].isoformat() + "Z")
    createdAt = fields.Function(lambda app: app["createdAt"].isoformat() + "Z")
    job = fields.Function(lambda app: app.get("job"))
    employer = fields.Function(lambda app: app.get("employer"))
    candidate = fields.Nested(CandidateProfileSchema(), allow_none=True)
    match = fields.Nested(MatchResultSchema(), allow_none=True)
    cvFileName = fields.Function(lambda app: app.get("cvFileName"))


class StatusUpdateSchema(BaseSchema):
    """Payload for a single application status transition.

    ``rejectionReason`` is only accepted alongside ``rejected``; sending it with
    any other target is rejected rather than silently dropped, so a client bug
    cannot lose a recruiter's explanation.
    """

    status = fields.Str(required=True, validate=validate.OneOf(list(REVIEW_STATUSES + CANDIDATE_STATUSES)))
    rejectionReason = fields.Str(allow_none=True)

    @validates_schema
    def _validate(self, data: dict, **kwargs) -> None:
        reason = data.get("rejectionReason")
        if reason is not None:
            reason = reason.strip()
            if not reason:
                data["rejectionReason"] = None
            elif len(reason) > MAX_REJECTION_REASON_LEN:
                raise ValidationError(
                    {"rejectionReason": f"Rejection reason must be at most {MAX_REJECTION_REASON_LEN} characters"}
                )
            else:
                data["rejectionReason"] = reason
        if data.get("rejectionReason") and data.get("status") != "rejected":
            raise ValidationError(
                {"rejectionReason": "A rejection reason can only be set when rejecting an application"}
            )


class BulkStatusUpdateSchema(BaseSchema):
    """Payload for moving several applications through the funnel at once."""

    applicationIds = fields.List(fields.Str(), required=True, validate=validate.Length(min=1, max=MAX_BULK_IDS))
    status = fields.Str(required=True, validate=validate.OneOf(list(REVIEW_STATUSES)))
    rejectionReason = fields.Str(allow_none=True)

    @validates_schema
    def _validate(self, data: dict, **kwargs) -> None:
        seen: set[str] = set()
        duplicates: list[str] = []
        for application_id in data["applicationIds"]:
            if application_id in seen:
                duplicates.append(application_id)
            seen.add(application_id)
        if duplicates:
            raise ValidationError(
                {"applicationIds": f"Duplicate application ids: {', '.join(sorted(set(duplicates)))}"}
            )
        reason = (data.get("rejectionReason") or "").strip()
        if reason and len(reason) > MAX_REJECTION_REASON_LEN:
            raise ValidationError(
                {"rejectionReason": f"Rejection reason must be at most {MAX_REJECTION_REASON_LEN} characters"}
            )
        data["rejectionReason"] = reason or None
        if data["rejectionReason"] and data["status"] != "rejected":
            raise ValidationError(
                {"rejectionReason": "A rejection reason can only be set when rejecting applications"}
            )


class NoteCreateSchema(BaseSchema):
    """Payload for adding a review note to an application."""

    body = fields.Str(required=True, validate=validate.Length(min=1, max=MAX_NOTE_LEN))

    @validates_schema
    def _validate(self, data: dict, **kwargs) -> None:
        body = (data.get("body") or "").strip()
        if not body:
            raise ValidationError({"body": "Note cannot be empty"})
        data["body"] = body


class ApplicationFiltersSchema(BaseSchema):
    """Validates the employer applicant-list query string.

    ``jobId`` is the wire name; ``job_id`` is the Python-side attribute the
    service reads. Every other public query param in this API is camelCase, so
    the exception is declared here rather than leaking a snake_case query param
    into the frontend.
    """

    job_id = fields.Str(required=True, data_key="jobId")
    status = fields.Str(validate=lambda v: _one_of(v, APPLICATION_STATUSES, "Status"))
    minScore = fields.Integer(validate=lambda v: _score_range(v))
    sort = fields.Str(validate=lambda v: _one_of(v, APPLICANT_SORTS, "Sort"))
    page = fields.Integer(validate=lambda v: _min(v, 1, "Page"))
    pageSize = fields.Integer(validate=lambda v: _page_size(v))

    @validates_schema
    def _validate(self, data: dict, **kwargs) -> None:
        data.setdefault("sort", "newest")
        data.setdefault("page", 1)
        data.setdefault("pageSize", PAGE_SIZE_DEFAULT)


def _one_of(value, allowed, label):
    if value not in allowed:
        raise ValidationError(f"{label} must be one of: " + ", ".join(allowed))
    return value


def _score_range(value):
    if value < 0 or value > 100:
        raise ValidationError("minScore must be between 0 and 100")
    return value


def _min(value, minimum, label):
    if value < minimum:
        raise ValidationError(f"{label} must be at least {minimum}")
    return value


def _page_size(value):
    if value < 1 or value > PAGE_SIZE_MAX:
        raise ValidationError(f"Page size must be between 1 and {PAGE_SIZE_MAX}")
    return value


application_schema = ApplicationSchema()
status_update_schema = StatusUpdateSchema()
bulk_status_update_schema = BulkStatusUpdateSchema()
note_create_schema = NoteCreateSchema()
application_filters_schema = ApplicationFiltersSchema()

__all__ = [
    "APPLICATION_STATUSES",
    "APPLICANT_SORTS",
    "CANDIDATE_STATUSES",
    "REVIEW_STATUSES",
    "ApplicationFiltersSchema",
    "ApplicationSchema",
    "BulkStatusUpdateSchema",
    "NoteCreateSchema",
    "StatusUpdateSchema",
    "application_filters_schema",
    "application_schema",
    "bulk_status_update_schema",
    "note_create_schema",
    "status_update_schema",
]
