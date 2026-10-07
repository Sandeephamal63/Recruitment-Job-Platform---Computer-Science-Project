import re

from marshmallow import ValidationError, fields, post_dump, validates_schema

from ..utils.urls import company_logo_url_for
from .base import BaseSchema

EMPLOYER = "employer"
CANDIDATE = "candidate"
ROLES = (EMPLOYER, CANDIDATE)

PASSWORD_MIN = 8
PASSWORD_MAX_BYTES = 72

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_NAME_LEN = 120
MAX_HEADLINE_LEN = 160
MAX_SKILLS = 40
MAX_SKILL_LEN = 60
MAX_COMPANY_DESCRIPTION_LEN = 2000

COMPANY_SIZES = ("1-10", "11-50", "51-200", "201-500", "501-1000", "1000+")


def _iso(value) -> str | None:
    return value.isoformat() + "Z" if value else None


def _clean_str(value, max_len: int) -> str:
    return (value or "").strip() if isinstance(value, str) else ""


def _validate_max(value: str, label: str, max_len: int) -> None:
    if len(value) > max_len:
        raise ValidationError(f"{label} must be at most {max_len} characters")


class UserSchema(BaseSchema):
    """Session wire shape of a user (dump side). Only whitelisted fields are
    serialized; passwordHash and cvParsedText never leave the server."""

    id = fields.Function(lambda user: str(user["_id"]))
    role = fields.Str()
    name = fields.Str()
    email = fields.Str()
    companyName = fields.Function(lambda user: (user or {}).get("companyName"))
    headline = fields.Function(lambda user: (user or {}).get("headline", ""))
    skills = fields.Function(lambda user: (user or {}).get("skills", []))
    createdAt = fields.Function(lambda user: user["createdAt"].isoformat() + "Z")

    @post_dump
    def _drop_irrelevant_role_keys(self, data: dict, **kwargs) -> dict:
        if data["role"] == EMPLOYER:
            data.pop("headline", None)
            data.pop("skills", None)
        else:
            data.pop("companyName", None)
        return data


class EmployerSummarySchema(BaseSchema):
    """Public, candidate-facing snapshot of the company behind a job.

    Exposed on job documents so a candidate can see *who* they are applying to
    (AGENTS: joined at read time, never denormalized onto the job).
    """

    id = fields.Function(lambda employer: str(employer["_id"]))
    name = fields.Str()
    companyName = fields.Function(lambda employer: employer.get("companyName") or employer.get("name"))
    companyDescription = fields.Function(lambda employer: employer.get("companyDescription") or "")
    companySize = fields.Function(lambda employer: employer.get("companySize") or "")
    companyIndustry = fields.Function(lambda employer: employer.get("companyIndustry") or "")
    companyLogoUrl = fields.Function(
        lambda employer: company_logo_url_for(employer, str(employer["_id"]))
    )


class UserCreateSchema(BaseSchema):
    """Validates and normalizes the /api/auth/register payload. All messaging is
    done in :meth:`_validate` so responses match the M1 error strings exactly;
    validated data is normalized in place (trimmed name, lowered email)."""

    role = fields.Str()
    name = fields.Str()
    email = fields.Str()
    password = fields.Str()
    companyName = fields.Str()
    headline = fields.Str()
    skills = fields.List(fields.Str())

    @validates_schema
    def _validate(self, data: dict, **kwargs) -> None:
        errors: dict[str, str] = {}

        role = data.get("role")
        if role not in ROLES:
            errors["role"] = "Role must be 'employer' or 'candidate'"

        name = (data.get("name") or "").strip()
        if not name:
            errors["name"] = "Name is required"
        elif len(name) > MAX_NAME_LEN:
            errors["name"] = f"Name must be at most {MAX_NAME_LEN} characters"

        email = (data.get("email") or "").strip().lower()
        if not email:
            errors["email"] = "Email is required"
        elif not EMAIL_RE.match(email):
            errors["email"] = "Email is not valid"

        password = data.get("password")
        if not isinstance(password, str) or not password:
            errors["password"] = "Password is required"
        elif len(password) < PASSWORD_MIN:
            errors["password"] = f"Password must be at least {PASSWORD_MIN} characters"
        elif len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
            errors["password"] = f"Password must be at most {PASSWORD_MAX_BYTES} bytes"

        company_name = (data.get("companyName") or "").strip() if isinstance(data.get("companyName"), str) else ""
        if role == EMPLOYER and not company_name:
            errors["companyName"] = "Company name is required"

        if errors:
            raise ValidationError(errors)

        data["name"] = name
        data["email"] = email
        data["companyName"] = company_name
        data["headline"] = ((data.get("headline") or "").strip() if isinstance(data.get("headline"), str) else "")
        data["skills"] = [
            skill.strip() for skill in data.get("skills", []) if isinstance(skill, str) and skill.strip()
        ]


class UserUpdateSchema(BaseSchema):
    """Partial update for PATCH /api/profile/me. Every field is optional; only
    role-relevant fields are accepted, and an employer may never set candidate
    fields (or vice versa) — that is a business rule, enforced by the schema so
    it is rejected at the boundary rather than silently ignored."""

    name = fields.Str()
    headline = fields.Str()
    skills = fields.List(fields.Str())
    companyName = fields.Str()
    companyDescription = fields.Str()
    companyIndustry = fields.Str()
    companySize = fields.Str()

    @validates_schema
    def _validate(self, data: dict, **kwargs) -> None:
        errors: dict[str, str] = {}
        role = (self.context or {}).get("role")

        if "name" in data:
            name = _clean_str(data.get("name"), MAX_NAME_LEN)
            if not name:
                errors["name"] = "Name is required"
            else:
                try:
                    _validate_max(name, "Name", MAX_NAME_LEN)
                    data["name"] = name
                except ValidationError as exc:
                    errors["name"] = exc.messages

        candidate_fields = {"headline", "skills"}
        employer_fields = {"companyName", "companyDescription", "companyIndustry", "companySize"}

        for key in candidate_fields & data.keys():
            if role == EMPLOYER:
                errors[key] = "This field is only available on candidate profiles"
        for key in employer_fields & data.keys():
            if role == CANDIDATE:
                errors[key] = "This field is only available on employer profiles"

        if "headline" in data and "headline" not in errors:
            headline = _clean_str(data.get("headline"), MAX_HEADLINE_LEN)
            try:
                _validate_max(headline, "Headline", MAX_HEADLINE_LEN)
                data["headline"] = headline
            except ValidationError as exc:
                errors["headline"] = exc.messages

        if "skills" in data and "skills" not in errors:
            skills = [
                _clean_str(skill, MAX_SKILL_LEN)
                for skill in data.get("skills") or []
                if isinstance(skill, str) and skill.strip()
            ]
            if len(skills) > MAX_SKILLS:
                errors["skills"] = f"Skills must be at most {MAX_SKILLS} entries"
            else:
                data["skills"] = skills

        for key in ("companyName", "companyIndustry", "companySize"):
            if key in data and key not in errors:
                data[key] = _clean_str(data.get(key), MAX_HEADLINE_LEN)
        if "companyDescription" in data and "companyDescription" not in errors:
            data["companyDescription"] = _clean_str(data.get("companyDescription"), MAX_COMPANY_DESCRIPTION_LEN)

        if "companySize" in data and data["companySize"] and data["companySize"] not in COMPANY_SIZES:
            errors["companySize"] = "Company size must be one of: " + ", ".join(COMPANY_SIZES)

        if errors:
            raise ValidationError(errors)


user_schema = UserSchema()
employer_summary_schema = EmployerSummarySchema()
user_create_schema = UserCreateSchema()
user_update_schema = UserUpdateSchema()

__all__ = [
    "COMPANY_SIZES",
    "CANDIDATE",
    "EMPLOYER",
    "ROLES",
    "EmployerSummarySchema",
    "UserCreateSchema",
    "UserSchema",
    "UserUpdateSchema",
    "employer_summary_schema",
    "user_create_schema",
    "user_schema",
    "user_update_schema",
]
