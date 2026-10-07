"""Auth + role-gating tests (M6-mandated).

Role gating is exercised against a dedicated role-probe route (no DB needed) so
the decorator contract is verified in isolation; registration/identity and the
password-at-rest guarantee run against a disposable Mongo database.
"""
import io
import re

import pytest

from app.db import get_db
from tests.conftest import auth_headers, minted_token, register
from tests.test_logo_validation import PNG_1PX


def test_role_required_rejects_candidate_and_anonymous(client, app):
    employer = minted_token(app, "employer")
    candidate = minted_token(app, "candidate")

    response = client.get("/api/test/role", headers=employer)
    assert response.status_code == 200

    response = client.get("/api/test/role", headers=candidate)
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"

    response = client.get("/api/test/role")
    assert response.status_code == 401


def test_token_without_role_claim_is_forbidden(client, app):
    import flask_jwt_extended

    with app.app_context():
        token = flask_jwt_extended.create_access_token(identity="no-role")
    response = client.get("/api/test/role", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@pytest.mark.parametrize("role,extra", [("candidate", {"headline": "Dev", "skills": ["Python"]}), ("employer", {"companyName": "Acme"})])
def test_register_login_and_me_roundtrip(db_client, role, extra):
    payload = register(db_client, role=role, **extra)
    assert payload["accessToken"]
    assert payload["refreshToken"]
    assert payload["user"]["email"]

    me = db_client.get("/api/auth/me", headers=auth_headers(payload))
    assert me.status_code == 200
    assert me.get_json()["data"]["role"] == role


def test_duplicate_email_conflict(db_client):
    email = "dupe-1790327000@test.dev"
    register(db_client, role="candidate", email=email)
    response = db_client.post(
        "/api/auth/register",
        json={"name": "Other", "email": email, "password": "password123", "role": "employer", "companyName": "Acme"},
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "email_taken"


def test_bad_password_is_rejected(db_client):
    payload = register(db_client, role="candidate")
    response = db_client.post(
        "/api/auth/login",
        json={"email": payload["user"]["email"], "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_credentials"


def test_password_hash_is_bcrypt_never_plaintext(db_app, db_client):
    password = "s3cret-pass"
    register(db_client, role="candidate", password=password, email="hash-1790327001@test.dev")
    with db_app.app_context():
        user = get_db().users.find_one({"email": "hash-1790327001@test.dev"})
    assert user is not None
    assert "password" not in user
    assert password not in user["passwordHash"]
    assert re.match(r"^\$2[aby]\$\d\d\$", user["passwordHash"])


def test_refresh_token_is_rotated_and_reuse_rejected(db_client):
    payload = register(db_client, role="candidate")
    old_token = payload["refreshToken"]

    first = db_client.post("/api/auth/refresh", json={"refreshToken": old_token})
    assert first.status_code == 200
    new_token = first.get_json()["data"]["refreshToken"]
    assert new_token != old_token

    reuse = db_client.post("/api/auth/refresh", json={"refreshToken": old_token})
    assert reuse.status_code == 401
    assert reuse.get_json()["error"]["code"] == "invalid_refresh_token"

    renewed = db_client.post("/api/auth/refresh", json={"refreshToken": new_token})
    assert renewed.status_code == 200


def test_malformed_refresh_token_rejected(db_client):
    register(db_client, role="candidate")
    response = db_client.post("/api/auth/refresh", json={"refreshToken": "not-a-token"})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_refresh_token"


def test_logout_revokes_refresh_token(db_client):
    payload = register(db_client, role="employer", companyName="Acme")

    logout = db_client.post(
        "/api/auth/logout", json={"refreshToken": payload["refreshToken"]}
    )
    assert logout.status_code == 200

    refresh = db_client.post("/api/auth/refresh", json={"refreshToken": payload["refreshToken"]})
    assert refresh.status_code == 401
    assert refresh.get_json()["error"]["code"] == "invalid_refresh_token"

    again = db_client.post("/api/auth/logout", json={"refreshToken": payload["refreshToken"]})
    assert again.status_code == 200


def test_short_password_rejected(db_client):
    response = db_client.post(
        "/api/auth/register",
        json={"name": "Shorty", "email": "short-1790327002@test.dev", "password": "short12", "role": "candidate"},
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_real_endpoint_requires_auth_and_role(db_client):
    response = db_client.post("/api/jobs", json={"title": "x"})
    assert response.status_code == 401

    candidate = register(db_client, role="candidate")
    forbidden = db_client.post("/api/jobs", headers=auth_headers(candidate), json={"title": "x"})
    assert forbidden.status_code == 403
    assert forbidden.get_json()["error"]["code"] == "forbidden"

    response = db_client.get("/api/applications/mine")
    assert response.status_code == 401


def test_recommendations_are_candidate_only(db_client):
    """Proactive recommendations are derived from a candidate's own CV, so an
    employer (or anyone unauthenticated) has no candidate profile to read."""
    candidate = register(
        db_client, role="candidate", headline="Backend engineer", skills=["Python"]
    )
    employer = register(db_client, role="employer", companyName="Acme")

    anonymous = db_client.get("/api/matching/recommendations")
    assert anonymous.status_code == 401

    forbidden = db_client.get("/api/matching/recommendations", headers=auth_headers(employer))
    assert forbidden.status_code == 403
    assert forbidden.get_json()["error"]["code"] == "forbidden"

    allowed = db_client.get("/api/matching/recommendations", headers=auth_headers(candidate))
    assert allowed.status_code == 200
    assert allowed.get_json()["success"] is True
    assert allowed.get_json()["data"]["recommendations"] == []


def test_recommendations_limit_is_bounded(db_client):
    candidate = register(db_client, role="candidate", skills=["Python"])
    response = db_client.get(
        "/api/matching/recommendations?limit=500", headers=auth_headers(candidate)
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_company_logo_upload_is_employer_only(db_client):
    """The two profile-upload routes split on role: a CV belongs to a candidate,
    a company logo to an employer. Each must refuse the other's role."""
    import io

    from tests.test_logo_validation import PNG_1PX

    candidate = register(db_client, role="candidate")
    employer = register(db_client, role="employer", companyName="Acme")

    as_candidate = db_client.post(
        "/api/profile/me/logo",
        headers=auth_headers(candidate),
        data={"logo": (io.BytesIO(PNG_1PX), "acme.png")},
        content_type="multipart/form-data",
    )
    assert as_candidate.status_code == 403
    assert as_candidate.get_json()["error"]["code"] == "forbidden"

    as_cv = db_client.post(
        "/api/profile/me/cv",
        headers=auth_headers(employer),
        data={"cv": (io.BytesIO(b"%PDF-1.4\n"), "cv.pdf")},
        content_type="multipart/form-data",
    )
    assert as_cv.status_code == 403

    anonymous = db_client.post("/api/profile/me/logo")
    assert anonymous.status_code == 401


def test_avatar_upload_is_candidate_only(db_client):
    """The mirror of ``test_company_logo_upload_is_employer_only``.

    Both image routes are role-gated, and in opposite directions: a logo belongs
    to an employer, an avatar to a candidate. Getting the pair the wrong way round
    would let a candidate brand themselves as a company.
    """
    candidate = register(db_client, role="candidate")
    employer = register(db_client, role="employer", companyName="Acme")

    forbidden = db_client.post(
        "/api/profile/me/avatar",
        headers=auth_headers(employer),
        data={"avatar": (io.BytesIO(PNG_1PX), "me.png")},
        content_type="multipart/form-data",
    )
    assert forbidden.status_code == 403
    assert forbidden.get_json()["error"]["code"] == "forbidden"

    forbidden_read = db_client.get("/api/profile/me/avatar", headers=auth_headers(employer))
    assert forbidden_read.status_code == 403

    forbidden_delete = db_client.delete("/api/profile/me/avatar", headers=auth_headers(employer))
    assert forbidden_delete.status_code == 403

    anonymous = db_client.post("/api/profile/me/avatar")
    assert anonymous.status_code == 401


def test_candidate_avatar_read_is_employer_only(db_client):
    """The employer-side read is the opposite gate: a candidate is not an
    employer, so they cannot walk another applicant's avatar route either."""
    candidate = register(db_client, role="candidate")

    response = db_client.get(
        "/api/profile/applications/000000000000000000000000/candidate-avatar",
        headers=auth_headers(candidate),
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"
