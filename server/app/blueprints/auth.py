from flask import Blueprint, current_app, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..schemas import user_create_schema, user_schema
from ..schemas.base import schema_load
from ..services import AuthService
from ..utils.errors import ValidationError
from ..utils.responses import created, ok

auth_bp = Blueprint("auth", __name__)


def _auth_service() -> AuthService:
    return current_app.extensions["services"]["auth"]


def _token_payload(user: dict, access_token: str, refresh_token: str) -> dict:
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "user": user_schema.dump(user),
    }


@auth_bp.post("/register")
def register():
    data = schema_load(user_create_schema, request.get_json(silent=True) or {})
    user = _auth_service().register_user(data)
    access_token, refresh_token = _auth_service().issue_tokens(user)
    return created(_token_payload(user, access_token, refresh_token))


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    user = _auth_service().authenticate(data.get("email"), data.get("password"))
    access_token, refresh_token = _auth_service().issue_tokens(user)
    return ok(_token_payload(user, access_token, refresh_token))


@auth_bp.post("/refresh")
def refresh():
    data = request.get_json(silent=True) or {}
    refresh_token = data.get("refreshToken")
    if not refresh_token:
        raise ValidationError(
            "Request validation failed",
            details=[{"field": "refreshToken", "message": "Refresh token is required"}],
        )
    access_token, new_refresh_token, user = _auth_service().rotate_refresh_token(refresh_token)
    return ok(_token_payload(user, access_token, new_refresh_token))


@auth_bp.post("/logout")
def logout():
    data = request.get_json(silent=True) or {}
    _auth_service().revoke_refresh_token(data.get("refreshToken"))
    return ok({"message": "Logged out"})


@auth_bp.get("/me")
@jwt_required()
def me():
    user = _auth_service().get_user_by_id(get_jwt_identity())
    return ok(user_schema.dump(user))