from typing import Any

from flask import jsonify


def ok(data: Any = None, meta: dict | None = None, status: int = 200):
    """Uniform success envelope for single resources and collections."""
    payload: dict[str, Any] = {"success": True, "data": data}
    if meta is not None:
        payload["meta"] = meta
    return jsonify(payload), status


def created(data: Any = None, meta: dict | None = None):
    return ok(data, meta, status=201)


def paginated(data: Any, page: int, page_size: int, total: int, extra: dict | None = None):
    """Success envelope for a page of a collection.

    ``totalPages``/``hasNext``/``hasPrevious`` are computed here rather than in
    the client so every paginated endpoint reports the same shape.
    """
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    pagination = {
        "page": page,
        "pageSize": page_size,
        "total": total,
        "totalPages": total_pages,
        "hasNext": page < total_pages,
        "hasPrevious": page > 1 and total > 0,
    }
    return ok(data, {"pagination": pagination, **(extra or {})})


def fail(code: str, message: str, status: int = 400, details: list | None = None):
    """Uniform error envelope. `code` is machine-readable, `message` human-facing."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return jsonify({"success": False, "error": error}), status