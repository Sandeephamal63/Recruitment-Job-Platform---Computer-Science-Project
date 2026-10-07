from marshmallow import ValidationError, fields, pre_load, validates_schema

from ..utils.time import end_of_day, utc_today
from .base import BaseSchema, split_list_fields
from .user import EmployerSummarySchema

EMPLOYMENT_TYPES = ("full-time", "part-time", "contract")
JOB_STATUSES = ("open", "closed")

EXPERIENCE_LEVELS = ("internship", "entry", "mid", "senior", "lead", "principal")
CURRENCIES = ("GBP", "USD", "EUR")

JOB_SORTS = ("newest", "oldest", "title")

MAX_TITLE_LEN = 120
MAX_SKILLS = 40
MIN_SALARY = 0
MAX_SALARY = 10_000_000

PAGE_SIZES = (12, 25, 50)
DEFAULT_PAGE_SIZE = 12
MAX_PAGE_SIZE = 50

employer_summary_schema = EmployerSummarySchema()


def dump_deadline(job: dict) -> str | None:
    """Serialize the stored end-of-day datetime back to the civil date the
    employer typed. A posting with no deadline is ``None``, not an absent key,
    so clients can treat the field as always present.

    Shared with ``SavedJobSchema``: a bookmarked vacancy has the same deadline
    and the same wire shape, and re-deriving the rule per schema is how the two
    projections would drift.
    """
    deadline = job.get("deadline")
    return deadline.date().isoformat() if deadline else None


class JobSchema(BaseSchema):
    """Wire shape of a job document (dump side). Only whitelisted fields are
    serialized; the raw MongoDB document stays internal.

    ``employer`` and ``applicantCount`` are joined at read time by the service
    so a candidate can see who posted the role and how contested it is.
    """

    id = fields.Function(lambda job: str(job["_id"]))
    employerId = fields.Function(lambda job: str(job.get("employerId")))
    title = fields.Str()
    description = fields.Str()
    requiredSkills = fields.List(fields.Str())
    location = fields.Str()
    employmentType = fields.Str()
    deadline = fields.Function(dump_deadline)
    salaryMin = fields.Function(lambda job: job.get("salaryMin"))
    salaryMax = fields.Function(lambda job: job.get("salaryMax"))
    currency = fields.Function(lambda job: job.get("currency") or "GBP")
    experienceLevel = fields.Function(lambda job: job.get("experienceLevel") or "")
    remote = fields.Function(lambda job: job.get("remote"))
    status = fields.Str()
    applicantCount = fields.Function(lambda job: job.get("applicantCount"))
    employer = fields.Function(lambda job: job.get("employer"))
    createdAt = fields.Function(lambda job: job["createdAt"].isoformat() + "Z")
    updatedAt = fields.Function(lambda job: job["updatedAt"].isoformat() + "Z")


class JobFiltersSchema(BaseSchema):
    """Validates the public browse query string (GET /api/jobs).

    Unknown values are rejected rather than ignored so a typo in a shared
    filter URL surfaces as a 422 instead of silently widening the result set.
    ``pageSize`` accepts any value up to ``MAX_PAGE_SIZE`` — ``PAGE_SIZES`` is
    the set the UI offers, not a whitelist the API enforces.
    """

    q = fields.Str()
    location = fields.Str()
    employmentType = fields.Str(validate=lambda v: _one_of(v, EMPLOYMENT_TYPES, "Employment type"))
    experienceLevel = fields.Str(validate=lambda v: _one_of(v, EXPERIENCE_LEVELS, "Experience level"))
    skills = fields.List(fields.Str())
    remote = fields.Boolean()
    salaryMin = fields.Integer(validate=lambda v: _range(v, "salaryMin"))
    sort = fields.Str(validate=lambda v: _one_of(v, JOB_SORTS, "Sort"))
    page = fields.Integer(validate=lambda v: _min(v, 1, "Page"))
    pageSize = fields.Integer(validate=lambda v: _min(v, 1, "Page size"))

    @pre_load
    def _accept_csv_lists(self, data, **kwargs):
        return split_list_fields(dict(data), ("skills",))
    @validates_schema
    def _validate(self, data: dict, **kwargs) -> None:
        if "salaryMin" in data and data["salaryMin"] is None:
            data.pop("salaryMin")
        for key in ("q", "location"):
            if key in data and isinstance(data[key], str):
                data[key] = data[key].strip() or None
                if data[key] is None:
                    data.pop(key)
        if "skills" in data:
            data["skills"] = [s.strip() for s in data["skills"] if isinstance(s, str) and s.strip()][:MAX_SKILLS]
            if not data["skills"]:
                data.pop("skills")
        data.setdefault("sort", "newest")
        data.setdefault("page", 1)
        data.setdefault("pageSize", DEFAULT_PAGE_SIZE)


def _one_of(value, allowed, label):
    if value not in allowed:
        raise ValidationError(f"{label} must be one of: " + ", ".join(str(a) for a in allowed))
    return value


def _range(value, label):
    if value < MIN_SALARY or value > MAX_SALARY:
        raise ValidationError(f"{label} must be between {MIN_SALARY} and {MAX_SALARY}")
    return value


def _min(value, minimum, label):
    if value < minimum:
        raise ValidationError(f"{label} must be at least {minimum}")
    return value


def _clean_titled_text(value: str | None, label: str, max_len: int) -> str:
    text = (value or "").strip() if isinstance(value, str) else ""
    if not text:
        raise ValidationError(f"{label} is required")
    if len(text) > max_len:
        raise ValidationError(f"{label} must be at most {max_len} characters")
    return text


def _normalize_skills(value) -> list[str]:
    return [
        skill.strip()
        for skill in (value or [])
        if isinstance(skill, str) and skill.strip()
    ][:MAX_SKILLS]


def _validate_deadline(data: dict, errors: dict) -> None:
    """Normalize the application deadline, shared by create and update.

    ``fields.Date`` has already rejected anything that isn't a bare
    ``YYYY-MM-DD`` by this point, so the only rule left is that the date is not
    in the past. The comparison is against *today* rather than the current
    instant: an employer whose role has already expired must still be able to
    move the deadline forward to revive it, and rejecting ``deadline < now``
    would make an end-of-day deadline impossible to set on the day itself.

    An explicit ``null`` clears the deadline rather than failing, so an employer
    who gave a closing date by mistake can withdraw it.
    """
    if "deadline" not in data:
        return
    day = data["deadline"]
    if day is None:
        data["deadline"] = None
        return
    if day < utc_today():
        errors["deadline"] = "Deadline cannot be in the past"
    data["deadline"] = end_of_day(day)


def _validate_compensation(data: dict, errors: dict) -> None:
    """Salary/remote coherence, shared by create and update."""
    currency = data.get("currency")
    if "currency" in data and currency not in CURRENCIES:
        errors["currency"] = "Currency must be one of: " + ", ".join(CURRENCIES)

    if "experienceLevel" in data and data["experienceLevel"] not in EXPERIENCE_LEVELS:
        errors["experienceLevel"] = "Experience level must be one of: " + ", ".join(EXPERIENCE_LEVELS)

    if "remote" in data and not isinstance(data["remote"], bool):
        errors["remote"] = "Remote must be true or false"

    for key in ("salaryMin", "salaryMax"):
        value = data.get(key)
        if key in data and value is not None and not isinstance(value, int):
            errors[key] = f"{key} must be a whole number"
        elif isinstance(value, int) and (value < MIN_SALARY or value > MAX_SALARY):
            errors[key] = f"{key} must be between {MIN_SALARY} and {MAX_SALARY}"

    if "salaryMin" in data and "salaryMax" in data:
        low, high = data.get("salaryMin"), data.get("salaryMax")
        if isinstance(low, int) and isinstance(high, int) and low > high:
            errors["salaryMax"] = "Maximum salary must be greater than or equal to the minimum"


class JobCreateSchema(BaseSchema):
    """Validates and normalizes the POST /api/jobs payload. ``status`` is not
    accepted on create — jobs always start open."""

    title = fields.Str()
    description = fields.Str()
    requiredSkills = fields.List(fields.Str())
    location = fields.Str()
    employmentType = fields.Str()
    salaryMin = fields.Integer()
    salaryMax = fields.Integer()
    currency = fields.Str()
    experienceLevel = fields.Str()
    remote = fields.Boolean()
    deadline = fields.Date(allow_none=True)

    @validates_schema
    def _validate(self, data: dict, **kwargs) -> None:
        errors: dict[str, str] = {}

        try:
            data["title"] = _clean_titled_text(data.get("title"), "Title", MAX_TITLE_LEN)
        except ValidationError as exc:
            errors["title"] = str(exc.messages[0] if isinstance(exc.messages, list) else exc.messages)

        description = (data.get("description") or "").strip() if isinstance(data.get("description"), str) else ""
        if not description:
            errors["description"] = "Description is required"

        location = (data.get("location") or "").strip() if isinstance(data.get("location"), str) else ""
        if not location:
            errors["location"] = "Location is required"

        employment_type = data.get("employmentType")
        if employment_type not in EMPLOYMENT_TYPES:
            errors["employmentType"] = "Employment type must be one of: " + ", ".join(EMPLOYMENT_TYPES)

        data["requiredSkills"] = _normalize_skills(data.get("requiredSkills"))
        _validate_compensation(data, errors)
        _validate_deadline(data, errors)

        if errors:
            raise ValidationError(errors)

        data["description"] = description
        data["location"] = location
        data["employmentType"] = employment_type


class JobUpdateSchema(BaseSchema):
    """Partial update payload for PATCH /api/jobs/:id. Every field is optional;
    present fields are validated and normalized in place."""

    title = fields.Str()
    description = fields.Str()
    requiredSkills = fields.List(fields.Str())
    location = fields.Str()
    employmentType = fields.Str()
    salaryMin = fields.Integer()
    salaryMax = fields.Integer()
    currency = fields.Str()
    experienceLevel = fields.Str()
    remote = fields.Boolean()
    status = fields.Str()
    deadline = fields.Date(allow_none=True)

    @validates_schema
    def _validate(self, data: dict, **kwargs) -> None:
        errors: dict[str, str] = {}

        if "title" in data:
            try:
                data["title"] = _clean_titled_text(data["title"], "Title", MAX_TITLE_LEN)
            except ValidationError as exc:
                errors["title"] = str(exc.messages[0] if isinstance(exc.messages, list) else exc.messages)

        if "description" in data:
            description = (data["description"] or "").strip() if isinstance(data["description"], str) else ""
            if not description:
                errors["description"] = "Description is required"

        if "location" in data:
            location = (data["location"] or "").strip() if isinstance(data["location"], str) else ""
            if not location:
                errors["location"] = "Location is required"

        if "employmentType" in data and data["employmentType"] not in EMPLOYMENT_TYPES:
            errors["employmentType"] = "Employment type must be one of: " + ", ".join(EMPLOYMENT_TYPES)

        if "status" in data and data["status"] not in JOB_STATUSES:
            errors["status"] = "Status must be open or closed"

        if "requiredSkills" in data:
            data["requiredSkills"] = _normalize_skills(data["requiredSkills"])

        _validate_compensation(data, errors)
        _validate_deadline(data, errors)

        if errors:
            raise ValidationError(errors)

        if "description" in data:
            data["description"] = description
        if "location" in data:
            data["location"] = location


job_schema = JobSchema()
job_filters_schema = JobFiltersSchema()
job_create_schema = JobCreateSchema()
job_update_schema = JobUpdateSchema()

__all__ = [
    "CURRENCIES",
    "DEFAULT_PAGE_SIZE",
    "EMPLOYMENT_TYPES",
    "EXPERIENCE_LEVELS",
    "JOB_SORTS",
    "JOB_STATUSES",
    "MAX_PAGE_SIZE",
    "PAGE_SIZES",
    "JobCreateSchema",
    "JobFiltersSchema",
    "JobSchema",
    "JobUpdateSchema",
    "dump_deadline",
    "job_create_schema",
    "job_filters_schema",
    "job_schema",
    "job_update_schema",
]
