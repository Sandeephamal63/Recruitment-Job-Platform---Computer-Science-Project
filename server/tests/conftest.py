import os
import uuid

os.environ.setdefault("MONGO_DB_NAME", "recruit_test")
os.environ.setdefault(
    "MATCH_EMBEDDINGS_DISABLED", "true"
)  # keep the suite model-free (stub/fake embedders + TF-IDF only)

import pytest
from flask_jwt_extended import create_access_token, jwt_required

from app import create_app
from app.db import ensure_indexes, get_db
from app.utils.responses import ok
from app.utils.roles import role_required
from config import Config


class TestConfig(Config):
    """Tests run against a disposable database and with rate limiting off so
    upload/matching limits never flake a suite."""

    MONGO_DB_NAME = "recruit_test"
    RATELIMIT_ENABLED = False
    TESTING = True


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    application.testing = True
    _register_role_probe(application)
    yield application


@pytest.fixture()
def db_app(app):
    """App backed by a fresh (dropped) Mongo database — local runs and CI both
    provide MongoDB via docker-compose / a CI service container."""
    with app.app_context():
        db = get_db()
        db.client.drop_database(db.name)
        ensure_indexes()
    yield app
    with app.app_context():
        get_db().client.drop_database(get_db().name)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db_client(db_app):
    return db_app.test_client()


@pytest.fixture()
def db(db_app):
    """The backing database, for the rare test that must reach past the API.

    Only for arranging a state the API deliberately refuses to produce — a job
    whose deadline has passed, which can otherwise only happen by waiting a day.
    Assertions still belong on the HTTP response, not here.
    """
    with db_app.app_context():
        yield get_db()


def _register_role_probe(app):
    @app.get("/api/test/role")
    @jwt_required()
    @role_required("employer")
    def role_probe():
        return ok({"ok": True})

    return app


def register(client, *, role, email=None, password="password123", **extra):
    payload = {
        "name": f"Test {role}",
        "email": email or f"{role}-{uuid.uuid4().hex[:10]}@test.dev",
        "password": password,
        "role": role,
    }
    payload.update(extra)
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def auth_headers(payload: dict) -> dict:
    return {"Authorization": f"Bearer {payload['accessToken']}"}


def minted_token(app, role: str) -> dict:
    with app.app_context():
        token = create_access_token(identity="probe-user", additional_claims={"role": role})
    return {"Authorization": f"Bearer {token}"}