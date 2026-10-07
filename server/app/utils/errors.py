from flask import Flask
from flask_jwt_extended import JWTManager
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from .responses import fail

_HTTP_CODE_MAP = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "too_many_requests",
    500: "internal_error",
}


class ApiError(Exception):
    """Base class for domain errors that map onto the uniform error envelope."""

    status = 400
    code = "bad_request"

    def __init__(
        self,
        message: str,
        code: str | None = None,
        status: int | None = None,
        details: list | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.status = status or self.status
        self.details = details


class ValidationError(ApiError):
    status = 422
    code = "validation_error"


class UnauthorizedError(ApiError):
    status = 401
    code = "unauthorized"


class ForbiddenError(ApiError):
    status = 403
    code = "forbidden"


class NotFoundError(ApiError):
    status = 404
    code = "not_found"


class ConflictError(ApiError):
    status = 409
    code = "conflict"


def register_error_handlers(app: Flask, jwt: JWTManager) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return fail(exc.code, exc.message, exc.status, exc.details)

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        code = _HTTP_CODE_MAP.get(exc.code, "http_error")
        return fail(code, exc.description or exc.name, exc.code or 500)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_entity_too_large(exc: RequestEntityTooLarge):
        # Whole-request cap in config, not a field-specific one: it stands in for
        # every upload (CV and company logo alike), so it must not name one.
        return fail(
            "upload_too_large",
            "Uploaded file is too large",
            422,
            details=[{"message": "The uploaded file exceeds the maximum request size."}],
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        app.logger.exception("Unhandled error")
        return fail("internal_error", "An unexpected error occurred", 500)

    @jwt.unauthorized_loader
    def handle_missing_token(reason: str):
        return fail("unauthorized", "Missing or invalid authorization token", 401)

    @jwt.invalid_token_loader
    def handle_invalid_token(reason: str):
        return fail("invalid_token", reason, 401)

    @jwt.expired_token_loader
    def handle_expired_token(jwt_header, jwt_payload):
        return fail("token_expired", "Access token has expired", 401)