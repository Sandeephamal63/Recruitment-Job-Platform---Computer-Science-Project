from marshmallow import fields

from .base import BaseSchema


class MatchResultSchema(BaseSchema):
    """Wire shape of a ``matchResults`` document (dump side).

    Values arrive through MatchService._serialize, which already normalises
    ids and timestamps for the wire, so fields pass through as-is.
    """

    applicationId = fields.Str()
    matchScore = fields.Integer(allow_none=True)
    matchedSkills = fields.List(fields.Str())
    missingSkills = fields.List(fields.Str())
    recommendations = fields.List(fields.Str())
    modelVersion = fields.Str()
    createdAt = fields.Str(allow_none=True)


match_result_schema = MatchResultSchema()