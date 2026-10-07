from marshmallow import fields, validate

from .base import BaseSchema

DEFAULT_RECOMMENDATION_LIMIT = 10
MAX_RECOMMENDATION_LIMIT = 50


class RecommendationSchema(BaseSchema):
    """One ranked job plus the evidence behind its score.

    Deliberately reuses the post-application field names (``matchScore``,
    ``matchedSkills``, ``missingSkills``, ``recommendations``) rather than
    inventing a parallel vocabulary: the score is produced by the same scorer,
    so the client renders both with the same components and the same
    ``scoreBand`` thresholds.
    """

    jobId = fields.Str()
    jobTitle = fields.Str()
    companyName = fields.Str()
    matchScore = fields.Integer()
    matchedSkills = fields.Function(lambda row: row.get("matchedSkills") or [])
    missingSkills = fields.Function(lambda row: row.get("missingSkills") or [])
    recommendations = fields.Function(lambda row: row.get("recommendations") or [])


class RecommendationsResponseSchema(BaseSchema):
    """The candidate's ranked list plus the stamp the cache is keyed on."""

    recommendations = fields.Function(
        lambda payload: recommendation_schema.dump(payload.get("recommendations") or [], many=True)
    )
    computedAt = fields.Function(
        lambda payload: payload["computedAt"].isoformat() + "Z" if payload.get("computedAt") else None
    )


class RecommendationQuerySchema(BaseSchema):
    limit = fields.Integer(
        load_default=DEFAULT_RECOMMENDATION_LIMIT,
        validate=validate.Range(min=1, max=MAX_RECOMMENDATION_LIMIT),
    )


recommendation_schema = RecommendationSchema()
recommendations_response_schema = RecommendationsResponseSchema()
recommendation_query_schema = RecommendationQuerySchema()

__all__ = [
    "DEFAULT_RECOMMENDATION_LIMIT",
    "MAX_RECOMMENDATION_LIMIT",
    "RecommendationQuerySchema",
    "RecommendationSchema",
    "RecommendationsResponseSchema",
    "recommendation_query_schema",
    "recommendation_schema",
    "recommendations_response_schema",
]
