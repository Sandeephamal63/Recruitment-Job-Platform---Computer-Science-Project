from flask import Blueprint, current_app, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from ..schemas.base import schema_load, schema_load_query
from ..schemas.job import (
    job_create_schema,
    job_filters_schema,
    job_schema,
    job_update_schema,
)
from ..schemas.stats import employer_overview_schema, job_funnel_schema
from ..services import JobService
from ..utils.responses import created, ok, paginated
from ..utils.roles import role_required

jobs_bp = Blueprint("jobs", __name__)


def _job_service() -> JobService:
    return current_app.extensions["services"]["jobs"]




@jobs_bp.get("/mine")
@jwt_required()
@role_required("employer")
def list_mine():
    jobs = _job_service().list_employer_jobs(get_jwt_identity())
    return ok(job_schema.dump(jobs, many=True))


@jobs_bp.get("/mine/overview")
@jwt_required()
@role_required("employer")
def employer_overview():
    """Headline counters for the employer dashboard."""
    overview = _job_service().employer_overview(get_jwt_identity())
    return ok(employer_overview_schema.dump(overview))


@jobs_bp.get("/mine/funnel")
@jwt_required()
@role_required("employer")
def employer_funnel():
    """Per-stage applicant counts for every job the employer owns."""
    funnel = _job_service().funnel_for_employer(get_jwt_identity())
    return ok(job_funnel_schema.dump(funnel, many=True))


@jobs_bp.post("")
@jwt_required()
@role_required("employer")
def create_job():
    data = schema_load(job_create_schema, request.get_json(silent=True) or {})
    job = _job_service().create_job(get_jwt_identity(), data)
    return created(job_schema.dump(job))


@jobs_bp.get("")
def list_open_jobs():
    """Public, paginated job browse."""
    filters = schema_load_query(job_filters_schema)
    jobs, total = _job_service().list_open_jobs(filters)
    return paginated(
        job_schema.dump(jobs, many=True),
        filters["page"],
        filters["pageSize"],
        total,
    )


@jobs_bp.get("/<job_id>")
@jwt_required(optional=True)
def get_job(job_id: str):
    viewer_id = get_jwt_identity()
    viewer_role = get_jwt().get("role")
    job = _job_service().get_job(job_id, viewer_id, viewer_role)
    return ok(job_schema.dump(job))


@jobs_bp.get("/<job_id>/funnel")
@jwt_required()
@role_required("employer")
def job_funnel(job_id: str):
    funnel = _job_service().funnel_for_job(job_id, get_jwt_identity())
    return ok(job_funnel_schema.dump(funnel))


@jobs_bp.patch("/<job_id>")
@jwt_required()
@role_required("employer")
def update_job(job_id: str):
    data = schema_load(job_update_schema, request.get_json(silent=True) or {})
    job = _job_service().update_job(job_id, get_jwt_identity(), data)
    return ok(job_schema.dump(job))
