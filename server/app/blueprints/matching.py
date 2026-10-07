from flask import Blueprint, current_app
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from .. import limiter
from ..schemas.base import schema_load_query
from ..schemas.match_result import match_result_schema
from ..schemas.recommendation import (
    recommendation_query_schema,
    recommendations_response_schema,
)
from ..services.match_service import MatchService
from ..services.recommendation_service import RecommendationService
from ..utils.rate_limits import MATCHING_LIMIT
from ..utils.responses import ok
from ..utils.roles import role_required


def _match_service() -> MatchService:
    return current_app.extensions["services"]["matching"]


def _recommendation_service() -> RecommendationService:
    return current_app.extensions["services"]["recommendations"]


matching_bp = Blueprint("matching", __name__)


@matching_bp.get("/mine")
@jwt_required()
@role_required("candidate")
@limiter.limit(MATCHING_LIMIT)
def list_my_results():
    results = _match_service().list_for_candidate(get_jwt_identity())
    return ok(match_result_schema.dump(results, many=True))


@matching_bp.get("/recommendations")
@jwt_required()
@role_required("candidate")
@limiter.limit(MATCHING_LIMIT)
def list_my_recommendations():
    """Ranked open jobs for the signed-in candidate, scored against their profile.

    Served from the per-candidate cache whenever it is no older than the
    candidate's profile, so a dashboard reload costs a read rather than a full
    pass over the open-job corpus.
    """
    query = schema_load_query(recommendation_query_schema)
    payload = _recommendation_service().recommendations_for_candidate(
        get_jwt_identity(), query["limit"]
    )
    return ok(recommendations_response_schema.dump(payload))


@matching_bp.get("/job/<job_id>/preview")
@jwt_required()
@role_required("candidate")
@limiter.limit(MATCHING_LIMIT)
def preview_for_job(job_id: str):
    result = _match_service().preview(job_id, get_jwt_identity())
    return ok(result)


@matching_bp.get("/<application_id>")
@jwt_required()
@limiter.limit(MATCHING_LIMIT)
def get_result(application_id: str):
    result = _match_service().get_or_run(
        application_id, get_jwt_identity(), get_jwt().get("role")
    )
    return ok(match_result_schema.dump(result))