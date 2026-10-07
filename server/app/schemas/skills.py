from marshmallow import fields

from .base import BaseSchema


class SkillSchema(BaseSchema):
    """One canonical skill from the matching gazetteer.

    Served from the same curated gazetteer the matching pipeline uses, so the
    skill picker a candidate types into is the exact vocabulary the scorer diffs
    against — a free-text field that invents "React 18" scores differently from
    "React", and the UI should not be able to do that silently.
    """

    name = fields.Str()
    aliases = fields.List(fields.Str())


skills_schema = SkillSchema()

__all__ = ["SkillSchema", "skills_schema"]
