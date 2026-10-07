import secrets
from datetime import timedelta

import bcrypt
from bson import ObjectId
from flask import current_app
from flask_jwt_extended import create_access_token
from pymongo.errors import DuplicateKeyError

from ..repositories.refresh_token_repository import RefreshTokenRepository
from ..repositories.user_repository import UserRepository
from ..utils.errors import ConflictError, NotFoundError, UnauthorizedError
from ..utils.time import utcnow

EMPLOYER = "employer"
CANDIDATE = "candidate"


def hash_password(password: str) -> str:
    rounds = current_app.config["BCRYPT_ROUNDS"]
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, TypeError):
        return False


class AuthService:
    """Authentication & token lifecycle. Both repositories are injected (never
    constructed ad hoc); the JWT calls are stateless helpers bound to the app
    config at request time."""

    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
    ):
        self._users = users
        self._refresh_tokens = refresh_tokens

    def register_user(self, data: dict) -> dict:
        """Persist a user whose payload was already validated by UserCreateSchema.

        ``data`` arrives normalized (trimmed name, lowered email, role-scoped
        profile fields); this service only owns uniqueness + the document shape.
        """
        if self._users.find_by_email(data["email"]):
            raise ConflictError("An account with this email already exists", code="email_taken")

        now = utcnow()
        document = {
            "role": data["role"],
            "name": data["name"],
            "email": data["email"],
            "passwordHash": hash_password(data["password"]),
            "createdAt": now,
        }
        if data["role"] == EMPLOYER:
            document["companyName"] = data["companyName"]
        else:
            document["headline"] = data["headline"]
            document["skills"] = data["skills"]
            # Seeds the stamp the candidate's recommendation cache is judged
            # against, so a brand-new account is considered fresh until their
            # first CV or skills edit.
            document["profileUpdatedAt"] = now

        try:
            user_id = self._users.create(document)
        except DuplicateKeyError:
            raise ConflictError("An account with this email already exists", code="email_taken")

        document["_id"] = ObjectId(user_id)
        return document

    def authenticate(self, email: str, password: str) -> dict:
        email = (email or "").strip().lower()
        user = self._users.find_by_email(email)
        if not user or not verify_password(password or "", user["passwordHash"]):
            raise UnauthorizedError("Invalid email or password", code="invalid_credentials")
        return user

    def get_user_by_id(self, user_id: str) -> dict:
        try:
            ObjectId(user_id)
        except Exception:
            raise UnauthorizedError("Invalid token identity", code="invalid_token")
        user = self._users.find_by_id(user_id)
        if not user:
            raise NotFoundError("User not found", code="user_not_found")
        return user

    def issue_tokens(self, user: dict) -> tuple[str, str]:
        access_token = create_access_token(
            identity=str(user["_id"]), additional_claims={"role": user["role"]}
        )
        return access_token, self._issue_refresh_token(user["_id"])

    def rotate_refresh_token(self, token: str) -> tuple[str, str, dict]:
        document = self._load_refresh_token(token)
        self._refresh_tokens.delete_by_id(document["_id"])
        user = self._users.find_by_id(str(document["userId"]))
        if not user:
            raise UnauthorizedError("Invalid refresh token", code="invalid_refresh_token")
        access_token, refresh_token = self.issue_tokens(user)
        return access_token, refresh_token, user

    def revoke_refresh_token(self, token: str | None) -> None:
        """Best-effort server-side revocation; idempotent so logout never leaks state."""
        if not token:
            return
        token_id = token.split(".", 1)[0]
        self._refresh_tokens.delete_by_token_id(token_id)

    def _issue_refresh_token(self, user_id: ObjectId) -> str:
        """Opaque token shaped `<tokenId>.<secret>`: tokenId is indexed for O(1)
        lookup, secret is bcrypt-hashed at rest."""
        token_id = secrets.token_urlsafe(16)
        secret = secrets.token_urlsafe(32)
        token_hash = bcrypt.hashpw(
            secret.encode(), bcrypt.gensalt(current_app.config["BCRYPT_ROUNDS"])
        ).decode()
        expires_at = utcnow() + timedelta(days=current_app.config["REFRESH_TOKEN_EXPIRES_DAYS"])
        self._refresh_tokens.create(
            {
                "tokenId": token_id,
                "tokenHash": token_hash,
                "userId": user_id,
                "expiresAt": expires_at,
                "createdAt": utcnow(),
            }
        )
        return f"{token_id}.{secret}"

    def _load_refresh_token(self, token: str) -> dict:
        try:
            token_id, secret = token.split(".", 1)
        except (AttributeError, ValueError):
            raise UnauthorizedError("Invalid refresh token", code="invalid_refresh_token")

        document = self._refresh_tokens.find_by_token_id(token_id)
        if not document:
            raise UnauthorizedError("Invalid refresh token", code="invalid_refresh_token")
        if document["expiresAt"] < utcnow():
            self._refresh_tokens.delete_by_id(document["_id"])
            raise UnauthorizedError("Refresh token has expired", code="refresh_token_expired")
        if not verify_password(secret, document["tokenHash"]):
            raise UnauthorizedError("Invalid refresh token", code="invalid_refresh_token")
        return document