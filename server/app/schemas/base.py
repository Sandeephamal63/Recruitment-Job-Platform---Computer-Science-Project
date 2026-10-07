from flask import request
from marshmallow import Schema, ValidationError

from ..utils.errors import ValidationError as ApiValidationError


class BaseSchema(Schema):
    """Base class for every request/response schema.

    Load errors are translated by :func:`schema_load` into the app's uniform
    ``ApiError(422, validation_error, details=[{field, message}])`` envelope so
    routes never hand-roll error mapping.
    """


def split_list_fields(data: dict, field_names: tuple[str, ...]) -> dict:
    """Accept a list field in a query string as either repeated params or CSV.

    ``?skills=Python&skills=Flask`` arrives from the route as a real list, but a
    hand-written or shared URL almost always reads ``?skills=Python,Flask``.
    Rejecting the second form would make every filterable share link fail, so
    both shapes are normalized here rather than in each route.
    """
    for name in field_names:
        value = data.get(name)
        if isinstance(value, str):
            data[name] = [item.strip() for item in value.split(",")]
    return data


def schema_load_query(schema: BaseSchema) -> dict:
    """Load a schema from the current request's query string.

    Only declared fields are read, using the wire name (``data_key`` when set),
    so a filter URL that has picked up a tracking parameter still resolves
    instead of 422-ing. Repeated keys collapse into a list; everything else is a
    scalar. Shared by the filterable list routes so none of them re-implements
    this.
    """
    raw: dict = {}
    for attribute, field in schema.fields.items():
        key = field.data_key or attribute
        values = request.args.getlist(key)
        if not values:
            continue
        raw[key] = values if len(values) > 1 else values[0]
    return schema_load(schema, raw)


def schema_load(schema: BaseSchema, data: dict) -> dict:
    try:
        return schema.load(data or {})
    except ValidationError as exc:
        raise ApiValidationError(
            "Request validation failed",
            details=_flatten(exc.messages),
        ) from exc


def _flatten(messages: dict) -> list[dict]:
    """Flatten marshmallow's ``{field: [message, ...]}`` into our details shape."""
    details: list[dict] = []
    for field_name, field_messages in messages.items():
        if isinstance(field_messages, dict):
            details.append({"field": field_name, "message": str(field_messages)})
        elif isinstance(field_messages, list):
            details.append({"field": field_name, "message": str(field_messages[0])})
        else:
            details.append({"field": field_name, "message": str(field_messages)})
    return details