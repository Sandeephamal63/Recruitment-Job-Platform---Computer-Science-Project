from io import BytesIO

from flask import Blueprint, current_app, request, send_file
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from .. import limiter
from ..schemas.base import schema_load
from ..schemas.profile import (
    profile_avatar_schema,
    profile_cv_schema,
    profile_logo_schema,
    profile_schema,
    saved_job_schema,
)
from ..schemas.user import user_update_schema
from ..services import ProfileService
from ..services.avatar_service import mimetype_for_avatar
from ..services.cv_service import mimetype_for
from ..services.logo_service import mimetype_for_logo
from ..utils.errors import ValidationError
from ..utils.rate_limits import UPLOAD_LIMIT
from ..utils.responses import created, ok
from ..utils.roles import role_required

profile_bp = Blueprint("profile", __name__)


def _profile_service() -> ProfileService:
    return current_app.extensions["services"]["profile"]


@profile_bp.get("/me")
@jwt_required()
def get_my_profile():
    return ok(profile_schema.dump(_profile_service().get_profile(get_jwt_identity())))


@profile_bp.patch("/me")
@jwt_required()
def update_my_profile():
    """Update the signed-in user's own profile fields.

    The schema is given the caller's role so a candidate cannot set company
    fields (or vice versa); the rejection happens at the API boundary rather
    than being silently ignored.
    """
    user_update_schema.context = {"role": get_jwt().get("role")}
    try:
        data = schema_load(user_update_schema, request.get_json(silent=True) or {})
    finally:
        user_update_schema.context = None
    user = _profile_service().update_profile(get_jwt_identity(), data)
    return ok(profile_schema.dump(user))


@profile_bp.post("/me/cv")
@jwt_required()
@role_required("candidate")
@limiter.limit(UPLOAD_LIMIT)
def upload_my_cv():
    cv = request.files.get("cv")
    if cv is None or not cv.filename:
        raise ValidationError(
            "Request validation failed",
            details=[{"field": "cv", "message": "A CV file is required"}],
        )
    result = _profile_service().upload_cv(get_jwt_identity(), cv)
    return created(profile_cv_schema.dump(result))


@profile_bp.get("/me/cv")
@jwt_required()
@role_required("candidate")
def download_my_cv():
    content, filename = _profile_service().download_cv(get_jwt_identity())
    return send_file(
        BytesIO(content),
        mimetype=mimetype_for(filename),
        as_attachment=True,
        download_name=filename,
    )


@profile_bp.delete("/me/cv")
@jwt_required()
@role_required("candidate")
def delete_my_cv():
    user = _profile_service().delete_cv(get_jwt_identity())
    return ok(profile_schema.dump(user))


@profile_bp.post("/me/logo")
@jwt_required()
@role_required("employer")
@limiter.limit(UPLOAD_LIMIT)
def upload_my_company_logo():
    logo = request.files.get("logo")
    if logo is None or not logo.filename:
        raise ValidationError(
            "Request validation failed",
            details=[{"field": "logo", "message": "A logo file is required"}],
        )
    result = _profile_service().upload_company_logo(get_jwt_identity(), logo)
    return created(profile_logo_schema.dump(result))


@profile_bp.post("/me/avatar")
@jwt_required()
@role_required("candidate")
@limiter.limit(UPLOAD_LIMIT)
def upload_my_avatar():
    avatar = request.files.get("avatar")
    if avatar is None or not avatar.filename:
        raise ValidationError(
            "Request validation failed",
            details=[{"field": "avatar", "message": "A profile photo is required"}],
        )
    result = _profile_service().upload_avatar(get_jwt_identity(), avatar)
    return created(profile_avatar_schema.dump(result))


@profile_bp.get("/me/avatar")
@jwt_required()
@role_required("candidate")
def download_my_avatar():
    """The caller's own avatar.

    Unlike the company logo this is authenticated, because the only reader is
    the signed-in candidate and there is no anonymous surface that needs it. The
    client therefore fetches the bytes through the API rather than pointing an
    ``<img>`` at a public URL.
    """
    content, filename = _profile_service().download_avatar(get_jwt_identity())
    return send_file(
        BytesIO(content),
        mimetype=mimetype_for_avatar(filename),
        as_attachment=False,
        download_name=filename,
    )


@profile_bp.delete("/me/avatar")
@jwt_required()
@role_required("candidate")
def delete_my_avatar():
    user = _profile_service().delete_avatar(get_jwt_identity())
    return ok(profile_schema.dump(user))


@profile_bp.get("/applications/<application_id>/candidate-avatar")
@jwt_required()
@role_required("employer")
def download_candidate_avatar(application_id: str):
    """An applicant's avatar, for the employer who owns the job they applied to.

    Keyed on the application rather than the candidate so the ownership check
    matches the applicant endpoints; see
    :meth:`ProfileService.download_candidate_avatar`.
    """
    content, filename = _profile_service().download_candidate_avatar(
        get_jwt_identity(), application_id
    )
    return send_file(
        BytesIO(content),
        mimetype=mimetype_for_avatar(filename),
        as_attachment=False,
        download_name=filename,
    )


@profile_bp.delete("/me/logo")
@jwt_required()
@role_required("employer")
def delete_my_company_logo():
    user = _profile_service().delete_company_logo(get_jwt_identity())
    return ok(profile_schema.dump(user))


@profile_bp.get("/employers/<employer_id>/logo")
def download_company_logo(employer_id: str):
    """Public so the landing page's employer strip renders for signed-out
    visitors. Serves the image bytes and nothing else.

    SVG is an accepted upload format, so the response is locked down: browsers
    never execute script in an SVG loaded through an ``<img>`` tag, and the CSP
    sandbox neutralises the remaining vector — a visitor navigating straight to
    this URL, where the file would otherwise become a document in our origin.
    ``nosniff`` stops the browser second-guessing the declared type.
    """
    content, filename = _profile_service().download_company_logo(employer_id)
    response = send_file(
        BytesIO(content),
        mimetype=mimetype_for_logo(filename),
        as_attachment=False,
        download_name=filename,
    )
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@profile_bp.get("/me/saved-jobs")
@jwt_required()
@role_required("candidate")
def list_saved_jobs():
    """The candidate's bookmarks, with the same company block browse shows."""
    jobs = _profile_service().list_saved_jobs(get_jwt_identity())
    jobs_service = current_app.extensions["services"]["jobs"]
    return ok(saved_job_schema.dump(jobs_service.enrich_with_employers(jobs), many=True))


@profile_bp.post("/me/saved-jobs/<job_id>")
@jwt_required()
@role_required("candidate")
def save_job(job_id: str):
    _profile_service().save_job(get_jwt_identity(), job_id)
    return created({"id": job_id})


@profile_bp.delete("/me/saved-jobs/<job_id>")
@jwt_required()
@role_required("candidate")
def unsave_job(job_id: str):
    _profile_service().remove_saved_job(get_jwt_identity(), job_id)
    return ok({"id": job_id})
