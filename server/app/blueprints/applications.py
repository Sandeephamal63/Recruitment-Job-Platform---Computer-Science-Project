from io import BytesIO

from flask import Blueprint, current_app, request, send_file
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from .. import limiter
from ..schemas.application import (
    application_filters_schema,
    application_schema,
    bulk_status_update_schema,
    note_create_schema,
    status_update_schema,
)
from ..schemas.application import NoteSchema
from ..schemas.base import schema_load, schema_load_query
from ..schemas.stats import score_distribution_schema
from ..services import ApplicationService
from ..services.cv_service import mimetype_for
from ..utils.errors import ValidationError
from ..utils.rate_limits import UPLOAD_LIMIT
from ..utils.responses import created, ok, paginated
from ..utils.roles import role_required

applications_bp = Blueprint("applications", __name__)

note_schema = NoteSchema()


def _application_service() -> ApplicationService:
    return current_app.extensions["services"]["applications"]


@applications_bp.get("/mine")
@jwt_required()
def list_mine():
    applications = _application_service().list_candidate_applications(get_jwt_identity())
    return ok(application_schema.dump(applications, many=True))


@applications_bp.get("/counts")
@jwt_required()
@role_required("employer")
def list_counts():
    counts = _application_service().counts_for_employer(get_jwt_identity())
    return ok(counts)


@applications_bp.get("")
@jwt_required()
@role_required("employer")
def list_for_job():
    """One page of a job's applicants, filtered and sorted in the database."""
    filters = schema_load_query(application_filters_schema)
    applications, total = _application_service().list_for_job(
        filters["job_id"],
        get_jwt_identity(),
        status=filters.get("status"),
        min_score=filters.get("minScore"),
        sort=filters.get("sort", "newest"),
        page=filters["page"],
        page_size=filters["pageSize"],
    )
    return paginated(
        application_schema.dump(applications, many=True),
        filters["page"],
        filters["pageSize"],
        total,
    )


@applications_bp.get("/scores")
@jwt_required()
@role_required("employer")
def employer_score_distribution():
    distribution = _application_service().employer_score_distribution(get_jwt_identity())
    return ok(score_distribution_schema.dump(distribution))


@applications_bp.get("/scores/<job_id>")
@jwt_required()
@role_required("employer")
def job_score_distribution(job_id: str):
    distribution = _application_service().score_distribution(job_id, get_jwt_identity())
    return ok(score_distribution_schema.dump(distribution))


@applications_bp.post("")
@jwt_required()
@role_required("candidate")
@limiter.limit(UPLOAD_LIMIT)
def create_application():
    """Submit an application, either with a fresh CV or the saved profile CV.

    ``useProfileCv`` lets a candidate who has already uploaded a CV to their
    profile apply without re-sending the same file; the stored bytes still go
    through the same validation and extraction path as an upload.
    """
    job_id = request.form.get("jobId")
    if not job_id:
        raise ValidationError(
            "Request validation failed",
            details=[{"field": "jobId", "message": "jobId is required"}],
        )
    use_profile_cv = str(request.form.get("useProfileCv", "")).lower() in {"1", "true", "yes"}
    cv = request.files.get("cv")
    if cv is not None and not cv.filename:
        cv = None
    if cv is None and not use_profile_cv:
        raise ValidationError(
            "Request validation failed",
            details=[{"field": "cv", "message": "A CV file is required"}],
        )
    application = _application_service().apply(
        job_id, get_jwt_identity(), cv, use_profile_cv=use_profile_cv
    )
    return created(application_schema.dump(application))


@applications_bp.patch("/bulk-status")
@jwt_required()
@role_required("employer")
def bulk_update_status():
    """Move several applications through the funnel in one action."""
    payload = schema_load(bulk_status_update_schema, request.get_json(silent=True) or {})
    result = _application_service().bulk_update_status(
        payload["applicationIds"],
        get_jwt_identity(),
        payload["status"],
        payload.get("rejectionReason"),
    )
    return ok(result)


@applications_bp.patch("/<application_id>/status")
@jwt_required()
@role_required("employer")
def update_status(application_id: str):
    payload = schema_load(status_update_schema, request.get_json(silent=True) or {})
    application = _application_service().update_status(
        application_id,
        get_jwt_identity(),
        payload["status"],
        payload.get("rejectionReason"),
    )
    return ok(application_schema.dump(application))


@applications_bp.post("/<application_id>/withdraw")
@jwt_required()
@role_required("candidate")
def withdraw(application_id: str):
    """Candidate-initiated withdrawal; valid until the application is closed."""
    application = _application_service().withdraw(application_id, get_jwt_identity())
    return ok(application_schema.dump(application))


@applications_bp.get("/<application_id>")
@jwt_required()
def get_application(application_id: str):
    application = _application_service().get_application(
        application_id, get_jwt_identity(), get_jwt().get("role")
    )
    return ok(application_schema.dump(application))


@applications_bp.get("/<application_id>/cv")
@jwt_required()
def stream_cv(application_id: str):
    content, filename = _application_service().stream_cv(
        application_id, get_jwt_identity(), get_jwt().get("role")
    )
    return send_file(
        BytesIO(content),
        mimetype=mimetype_for(filename),
        as_attachment=True,
        download_name=filename,
    )


@applications_bp.get("/<application_id>/notes")
@jwt_required()
@role_required("employer")
def list_notes(application_id: str):
    notes = _application_service().list_notes(application_id, get_jwt_identity())
    return ok(note_schema.dump(notes, many=True))


@applications_bp.post("/<application_id>/notes")
@jwt_required()
@role_required("employer")
def add_note(application_id: str):
    payload = schema_load(note_create_schema, request.get_json(silent=True) or {})
    notes = _application_service().add_note(
        application_id, get_jwt_identity(), payload["body"]
    )
    return created(note_schema.dump(notes, many=True))


@applications_bp.delete("/<application_id>/notes/<note_id>")
@jwt_required()
@role_required("employer")
def remove_note(application_id: str, note_id: str):
    _application_service().remove_note(application_id, get_jwt_identity(), note_id)
    return ok({"removed": note_id})