from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from ..schemas.skills import skills_schema
from ..services.skills_service import catalogue, suggest
from ..utils.errors import ValidationError
from ..utils.responses import ok

skills_bp = Blueprint("skills", __name__)

MAX_QUERY_LEN = 60


@skills_bp.get("")
@jwt_required(optional=True)
def list_skills():
    """The curated skills catalogue, shared with the matching gazetteer.

    Public: a visitor browsing jobs can see the vocabulary the platform scores
    against before deciding to register. With ``?q=`` the same route becomes the
    type-ahead behind the skill inputs, returning plain canonical names under
    ``results`` — a deliberately different key from the full ``skills`` objects,
    so a client can never read a name out of one and expect an object from the
    other.
    """
    query = request.args.get("q")
    if query is None:
        entries = catalogue()
        return ok({"skills": skills_schema.dump(entries, many=True), "count": len(entries)})

    if len(query) > MAX_QUERY_LEN:
        raise ValidationError(
            "Request validation failed",
            details=[{"field": "q", "message": f"Search term must be at most {MAX_QUERY_LEN} characters"}],
        )
    results = suggest(query)
    return ok({"results": results, "count": len(results)})
