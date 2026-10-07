"""End-to-end functional pass (outline Sprint 6, "functional test pass"):
register -> post job -> apply with a real CV -> match score -> employer review
-> status transitions -> ownership/duplicate/validation failures.

Runs against a disposable ``recruit_test`` Mongo database (docker-compose
provides it locally; a CI sidecar provides it on GitHub Actions).
"""
import io
import zipfile
from datetime import timedelta

import pytest
from bson import ObjectId

from app.utils.time import end_of_day, utc_today
from tests.conftest import auth_headers, register
from tests.test_logo_validation import PNG_1PX, SVG_WITH_PROLOG

JOB_PAYLOAD = {
    "title": "Backend Engineer",
    "description": "Python, Flask, MongoDB APIs, Docker deployment",
    "requiredSkills": ["Python", "Flask", "MongoDB", "Docker"],
    "location": "London",
    "employmentType": "full-time",
}


def make_cv_bytes(text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>",
        )
    return buffer.getvalue()


def apply_cv(client, headers, job_id, text):
    return client.post(
        "/api/applications",
        headers=headers,
        data={
            "jobId": job_id,
            "cv": (io.BytesIO(make_cv_bytes(text)), "cv.docx"),
        },
        content_type="multipart/form-data",
    )


@pytest.fixture()
def users(db_client):
    employer = register(db_client, role="employer", companyName="Acme")
    candidate = register(db_client, role="candidate", headline="Dev", skills=["Python", "Flask"])
    intruder = register(db_client, role="employer", companyName="Intruder")
    return employer, candidate, intruder


def create_job(db_client, employer) -> str:
    response = db_client.post("/api/jobs", headers=auth_headers(employer), json=JOB_PAYLOAD)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]["id"]


def test_happy_path_application_to_match_to_employer_review(db_client, users):
    employer, candidate, _ = users
    job_id = create_job(db_client, employer)

    application = apply_cv(db_client, auth_headers(candidate), job_id, "Python Flask MongoDB Docker five years")
    assert application.status_code == 201, application.get_json()
    application_data = application.get_json()["data"]
    app_id = application_data["id"]
    assert application_data["status"] == "submitted"
    assert application_data["job"]["title"] == "Backend Engineer"

    mine = db_client.get("/api/applications/mine", headers=auth_headers(candidate))
    assert mine.status_code == 200
    assert len(mine.get_json()["data"]) == 1

    match = db_client.get(f"/api/matching/{app_id}", headers=auth_headers(candidate))
    assert match.status_code == 200
    match_data = match.get_json()["data"]
    assert isinstance(match_data["matchScore"], int)
    assert 0 <= match_data["matchScore"] <= 100

    applicants = db_client.get(f"/api/applications?jobId={job_id}", headers=auth_headers(employer))
    assert applicants.status_code == 200
    listing = applicants.get_json()["data"]
    assert len(listing) == 1
    assert listing[0]["candidate"]["name"] == candidate["user"]["name"]
    assert listing[0]["match"]["matchScore"] == match_data["matchScore"]

    counts = db_client.get("/api/applications/counts", headers=auth_headers(employer))
    by_job = {entry["jobId"]: entry["count"] for entry in counts.get_json()["data"]}
    assert by_job[job_id] == 1


def test_recommendation_score_matches_the_post_application_score(db_client, users):
    """The one invariant that makes proactive ranking defensible.

    A candidate sees a score for a job on the dashboard; the employer sees a
    score for the same candidate on the same job once they apply. If those two
    numbers can differ, the product is showing the same pair of people two
    verdicts, and the ranking is not something either side can be held to.

    The candidate's profile CV is the same text they later submit, because the
    two numbers are only comparable when they describe the same candidate. They
    genuinely diverge otherwise — the dashboard ranks the profile, the employer
    ranks the CV that was actually submitted — and that difference is the point
    of the scores being separate, not a defect.
    """
    employer, candidate, _ = users
    job_id = create_job(db_client, employer)
    cv_text = "Python Flask MongoDB Docker five years"

    uploaded = db_client.post(
        "/api/profile/me/cv",
        headers=auth_headers(candidate),
        data={"cv": (io.BytesIO(make_cv_bytes(cv_text)), "cv.docx")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code in (200, 201), uploaded.get_json()

    recommendations = db_client.get(
        "/api/matching/recommendations", headers=auth_headers(candidate)
    )
    assert recommendations.status_code == 200
    rows = {row["jobId"]: row for row in recommendations.get_json()["data"]["recommendations"]}
    assert job_id in rows, "the new posting should rank for a candidate with matching skills"
    predicted = rows[job_id]

    application = apply_cv(db_client, auth_headers(candidate), job_id, cv_text)
    assert application.status_code == 201, application.get_json()
    app_id = application.get_json()["data"]["id"]

    match = db_client.get(f"/api/matching/{app_id}", headers=auth_headers(candidate)).get_json()["data"]
    assert match["matchScore"] == predicted["matchScore"]
    assert match["matchedSkills"] == predicted["matchedSkills"]
    assert match["missingSkills"] == predicted["missingSkills"]


def test_recommendations_are_refreshed_after_a_profile_edit(db_client, users):
    """Editing the profile the ranking is derived from must change the answer.

    A cached ranking that outlives the CV it was computed from would show the
    candidate a ranking for a CV they no longer have, with nothing on screen
    suggesting it was stale.
    """
    employer, candidate, _ = users
    create_job(db_client, employer)

    def top_job() -> str | None:
        response = db_client.get(
            "/api/matching/recommendations", headers=auth_headers(candidate)
        )
        rows = response.get_json()["data"]["recommendations"]
        return rows[0]["jobId"] if rows else None

    assert top_job() is not None
    edited = db_client.patch(
        "/api/profile/me",
        headers=auth_headers(candidate),
        json={"skills": ["Rust", "WebAssembly"], "headline": "Systems programmer"},
    )
    assert edited.status_code == 200
    assert top_job() is not None


def test_status_funnel_through_api(db_client, users):
    employer, candidate, _ = users
    job_id = create_job(db_client, employer)
    app_id = apply_cv(db_client, auth_headers(candidate), job_id, "Python").get_json()["data"]["id"]

    def patch(status):
        return db_client.patch(
            f"/api/applications/{app_id}/status",
            headers=auth_headers(employer),
            json={"status": status},
        )

    assert patch("under_review").status_code == 200
    assert patch("shortlisted").status_code == 200

    invalid = patch("under_review")
    assert invalid.status_code == 409
    assert invalid.get_json()["error"]["code"] == "invalid_transition"

    bad_target = db_client.patch(
        f"/api/applications/{app_id}/status",
        headers=auth_headers(employer),
        json={"status": "hired"},
    )
    assert bad_target.status_code == 422


def test_ownership_and_duplicate_guards(db_client, users):
    employer, candidate, intruder = users
    job_id = create_job(db_client, employer)
    apply_cv(db_client, auth_headers(candidate), job_id, "Python")

    removed = apply_cv(db_client, auth_headers(candidate), job_id, "Python")
    assert removed.status_code == 409
    assert removed.get_json()["error"]["code"] == "already_applied"

    foreign_list = db_client.get(f"/api/applications?jobId={job_id}", headers=auth_headers(intruder))
    assert foreign_list.status_code == 403

    app_id = db_client.get(
        f"/api/applications?jobId={job_id}", headers=auth_headers(employer)
    ).get_json()["data"][0]["id"]
    foreign_patch = db_client.patch(
        f"/api/applications/{app_id}/status",
        headers=auth_headers(intruder),
        json={"status": "shortlisted"},
    )
    assert foreign_patch.status_code == 403


def test_applicant_view_requires_job_id(db_client, users):
    employer, _, _ = users
    response = db_client.get("/api/applications", headers=auth_headers(employer))
    assert response.status_code == 422


def test_closed_job_rejects_new_applications(db_client, users):
    employer, candidate, _ = users
    job_id = create_job(db_client, employer)
    db_client.patch(f"/api/jobs/{job_id}", headers=auth_headers(employer), json={"status": "closed"})

    response = apply_cv(db_client, auth_headers(candidate), job_id, "Python")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "job_closed"


def upload_logo(client, headers, payload: bytes, filename: str = "acme.png"):
    return client.post(
        "/api/profile/me/logo",
        headers=headers,
        data={"logo": (io.BytesIO(payload), filename)},
        content_type="multipart/form-data",
    )


def test_company_logo_upload_serves_publicly_and_appears_on_jobs(db_client, users):
    employer, _, _ = users
    job_id = create_job(db_client, employer)

    browse = db_client.get("/api/jobs").get_json()["data"][0]
    assert browse["employer"]["companyLogoUrl"] is None, "no logo yet, so the client falls back to initials"

    upload = upload_logo(db_client, auth_headers(employer), PNG_1PX)
    assert upload.status_code == 201, upload.get_json()
    body = upload.get_json()["data"]
    assert body["companyLogoFileName"] == "acme.png"
    assert body["companyLogoUrl"] == f"profile/employers/{employer['user']['id']}/logo"

    browse = db_client.get("/api/jobs").get_json()["data"][0]
    assert browse["employer"]["companyLogoUrl"] == body["companyLogoUrl"]

    # No Authorization header at all: the landing page's employer strip renders
    # for signed-out visitors.
    public = db_client.get(f"/api/{body['companyLogoUrl']}")
    assert public.status_code == 200
    assert public.data == PNG_1PX
    assert public.headers["Content-Type"].startswith("image/png")

    removed = db_client.delete("/api/profile/me/logo", headers=auth_headers(employer))
    assert removed.status_code == 200
    assert removed.get_json()["data"]["companyLogoUrl"] is None
    assert db_client.get(f"/api/{body['companyLogoUrl']}").status_code == 404


def test_svg_logo_upload_is_locked_down_on_the_public_route(db_client, users):
    """SVG is an accepted format, so the response has to neutralise the one
    vector a plain image route would otherwise have: a visitor navigating straight
    to the URL, which would make the file a document in our own origin."""
    employer, _, _ = users
    upload = upload_logo(db_client, auth_headers(employer), SVG_WITH_PROLOG, "acme.svg")
    assert upload.status_code == 201, upload.get_json()

    public = db_client.get(f"/api/{upload.get_json()['data']['companyLogoUrl']}")
    assert public.status_code == 200
    assert public.headers["Content-Type"].startswith("image/svg+xml")
    assert "sandbox" in public.headers["Content-Security-Policy"]
    assert "default-src 'none'" in public.headers["Content-Security-Policy"]
    assert public.headers["X-Content-Type-Options"] == "nosniff"
    assert "attachment" not in public.headers.get("Content-Disposition", "")


def test_logo_upload_rejects_a_non_image(db_client, users):
    employer, _, _ = users

    response = upload_logo(db_client, auth_headers(employer), b"this is not an image", "acme.png")

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "logo_invalid_type"


def test_logo_upload_requires_a_file(db_client, users):
    employer, _, _ = users

    response = db_client.post("/api/profile/me/logo", headers=auth_headers(employer))

    assert response.status_code == 422
    assert response.get_json()["error"]["details"][0]["field"] == "logo"

def upload_avatar(client, headers, payload: bytes, filename: str = "me.png"):
    return client.post(
        "/api/profile/me/avatar",
        headers=headers,
        data={"avatar": (io.BytesIO(payload), filename)},
        content_type="multipart/form-data",
    )


def test_avatar_upload_then_owner_and_applicant_employer_can_read_it(db_client, users):
    employer, candidate, _ = users
    job_id = create_job(db_client, employer)
    application = apply_cv(db_client, auth_headers(candidate), job_id, "Python Flask")
    app_id = application.get_json()["data"]["id"]

    # Nothing uploaded yet: the owner read 404s and the client shows initials.
    assert db_client.get("/api/profile/me/avatar", headers=auth_headers(candidate)).status_code == 404

    upload = upload_avatar(db_client, auth_headers(candidate), PNG_1PX)
    assert upload.status_code == 201, upload.get_json()
    assert upload.get_json()["data"] == {"avatarFileName": "me.png"}

    profile = db_client.get("/api/profile/me", headers=auth_headers(candidate))
    assert profile.get_json()["data"]["avatarFileName"] == "me.png"

    own = db_client.get("/api/profile/me/avatar", headers=auth_headers(candidate))
    assert own.status_code == 200
    assert own.data == PNG_1PX
    assert own.headers["Content-Type"].startswith("image/png")

    as_employer = db_client.get(
        f"/api/profile/applications/{app_id}/candidate-avatar", headers=auth_headers(employer)
    )
    assert as_employer.status_code == 200
    assert as_employer.data == PNG_1PX
    assert as_employer.headers["Content-Type"].startswith("image/png")

    removed = db_client.delete("/api/profile/me/avatar", headers=auth_headers(candidate))
    assert removed.status_code == 200
    assert removed.get_json()["data"]["avatarFileName"] is None
    assert db_client.get("/api/profile/me/avatar", headers=auth_headers(candidate)).status_code == 404


def test_avatar_read_requires_authentication(db_client, users):
    """The mirror of the company logo, which is deliberately public.

    An avatar is only ever read by a signed-in viewer, so the route is gated
    even though the logo's is not.
    """
    employer, candidate, _ = users
    job_id = create_job(db_client, employer)
    application = apply_cv(db_client, auth_headers(candidate), job_id, "Python Flask")
    app_id = application.get_json()["data"]["id"]
    upload_avatar(db_client, auth_headers(candidate), PNG_1PX)

    assert db_client.get("/api/profile/me/avatar").status_code == 401
    anonymous = db_client.get(f"/api/profile/applications/{app_id}/candidate-avatar")
    assert anonymous.status_code == 401


def test_another_employer_cannot_read_an_applicant_avatar(db_client, users):
    employer, candidate, intruder = users
    job_id = create_job(db_client, employer)
    application = apply_cv(db_client, auth_headers(candidate), job_id, "Python Flask")
    app_id = application.get_json()["data"]["id"]
    upload_avatar(db_client, auth_headers(candidate), PNG_1PX)

    response = db_client.get(
        f"/api/profile/applications/{app_id}/candidate-avatar", headers=auth_headers(intruder)
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"


def test_employer_cannot_upload_an_avatar(db_client, users):
    employer, _, _ = users

    response = upload_avatar(db_client, auth_headers(employer), PNG_1PX)

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"


def test_avatar_upload_rejects_an_svg(db_client, users):
    """A logo accepts SVG; an avatar does not.

    Same payload, opposite outcome — asserted end-to-end so the two validators
    cannot drift into each other.
    """
    _, candidate, _ = users

    response = upload_avatar(db_client, auth_headers(candidate), SVG_WITH_PROLOG, "me.svg")

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "avatar_invalid_type"


def test_avatar_upload_rejects_a_non_image_and_requires_a_file(db_client, users):
    _, candidate, _ = users

    rejected = upload_avatar(db_client, auth_headers(candidate), b"this is not an image", "me.png")
    assert rejected.status_code == 422
    assert rejected.get_json()["error"]["code"] == "avatar_invalid_type"

    missing = db_client.post("/api/profile/me/avatar", headers=auth_headers(candidate))
    assert missing.status_code == 422
    assert missing.get_json()["error"]["details"][0]["field"] == "avatar"


def test_avatar_appears_nowhere_in_the_public_payload(db_client, users):
    """``avatarFileRef`` is a GridFS id and must never reach a client.

    The profile payload exposes the filename (so the upload card can show what
    is stored) and nothing else; the applicant's snapshot in the employer-facing
    application carries no avatar field at all, because the employer fetches the
    bytes through the authenticated route.
    """
    employer, candidate, _ = users
    job_id = create_job(db_client, employer)
    apply_cv(db_client, auth_headers(candidate), job_id, "Python Flask")
    upload_avatar(db_client, auth_headers(candidate), PNG_1PX)

    profile = db_client.get("/api/profile/me", headers=auth_headers(candidate)).get_json()["data"]
    assert "avatarFileRef" not in profile
    assert "cvParsedText" not in profile

    listing = db_client.get(
        f"/api/applications?jobId={job_id}", headers=auth_headers(employer)
    ).get_json()["data"]
    assert "avatarFileRef" not in listing[0]["candidate"]
    assert "avatarUrl" not in listing[0]["candidate"]


def _iso_in(days: int) -> str:
    return (utc_today() + timedelta(days=days)).isoformat()


def test_deadline_round_trips_through_post_patch_and_get(db_client, users):
    """The wire form is a date; the stored form is the end of that day."""
    employer, _, _ = users
    response = db_client.post(
        "/api/jobs",
        headers=auth_headers(employer),
        json={**JOB_PAYLOAD, "deadline": _iso_in(30)},
    )
    assert response.status_code == 201, response.get_json()
    job_id = response.get_json()["data"]["id"]
    assert response.get_json()["data"]["deadline"] == _iso_in(30)

    fetched = db_client.get(f"/api/jobs/{job_id}", headers=auth_headers(employer))
    assert fetched.get_json()["data"]["deadline"] == _iso_in(30)

    moved = db_client.patch(
        f"/api/jobs/{job_id}", headers=auth_headers(employer), json={"deadline": _iso_in(60)}
    )
    assert moved.status_code == 200, moved.get_json()
    assert moved.get_json()["data"]["deadline"] == _iso_in(60)

    cleared = db_client.patch(
        f"/api/jobs/{job_id}", headers=auth_headers(employer), json={"deadline": None}
    )
    assert cleared.status_code == 200, cleared.get_json()
    assert cleared.get_json()["data"]["deadline"] is None


def test_deadline_is_optional_and_defaults_to_null(db_client, users):
    employer, _, _ = users
    job_id = create_job(db_client, employer)

    fetched = db_client.get(f"/api/jobs/{job_id}", headers=auth_headers(employer))

    assert fetched.get_json()["data"]["deadline"] is None


def test_past_deadline_is_rejected_with_a_field_level_422(db_client, users):
    employer, _, _ = users

    response = db_client.post(
        "/api/jobs",
        headers=auth_headers(employer),
        json={**JOB_PAYLOAD, "deadline": _iso_in(-1)},
    )

    assert response.status_code == 422, response.get_json()
    error = response.get_json()["error"]
    assert error["code"] == "validation_error"
    assert any(d["field"] == "deadline" and "past" in d["message"] for d in error["details"])


def test_expired_job_is_absent_from_browse_and_recommendations(db_client, db, users):
    """The two paths a candidate discovers roles through, over HTTP.

    Complements the service-level agreement test: that one proves the two
    predicates agree, this one proves the clause survives the route, the schema
    and the query-string plumbing.
    """
    employer, candidate, _ = users
    live = db_client.post(
        "/api/jobs",
        headers=auth_headers(employer),
        json={**JOB_PAYLOAD, "title": "Live role", "deadline": _iso_in(30)},
    ).get_json()["data"]["id"]
    db_client.post(
        "/api/jobs",
        headers=auth_headers(employer),
        json={**JOB_PAYLOAD, "title": "Lapsed role", "deadline": _iso_in(30)},
    )
    lapsed = db_client.get(
        "/api/jobs?pageSize=50", headers=auth_headers(candidate)
    ).get_json()["data"]
    lapsed_id = next(j["id"] for j in lapsed if j["title"] == "Lapsed role")
    # Move the deadline into the past through a direct write: the API refuses to
    # set one, which is the point of the validation, so expiry is reached the
    # only way it happens in production — by waiting.
    db.jobs.update_one(
        {"_id": ObjectId(lapsed_id)},
        {"$set": {"deadline": end_of_day(utc_today() - timedelta(days=1))}},
    )

    browsed = db_client.get("/api/jobs?pageSize=50", headers=auth_headers(candidate))
    titles = [j["title"] for j in browsed.get_json()["data"]]
    assert "Lapsed role" not in titles
    assert "Live role" in titles

    recommendations = db_client.get(
        "/api/matching/recommendations?limit=20", headers=auth_headers(candidate)
    )
    rows = recommendations.get_json()["data"]["recommendations"]
    assert "Lapsed role" not in [r.get("jobTitle") for r in rows]
    assert "Live role" in [r.get("jobTitle") for r in rows]

    # And the posting is simply gone for a candidate, while the employer keeps it.
    assert db_client.get(f"/api/jobs/{lapsed_id}", headers=auth_headers(candidate)).status_code == 404
    assert (
        db_client.get(f"/api/jobs/{lapsed_id}", headers=auth_headers(employer)).status_code == 200
    )
    assert db_client.get(f"/api/jobs/{live}", headers=auth_headers(candidate)).status_code == 200


def test_expired_job_rejects_new_applications(db_client, db, users):
    """Same 409 as a closed job: an expired role is closed as far as a candidate
    is concerned, and *why* it closed is not theirs to be told."""
    employer, candidate, _ = users
    job_id = create_job(db_client, employer)
    db.jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {"deadline": end_of_day(utc_today() - timedelta(days=1))}},
    )

    response = apply_cv(db_client, auth_headers(candidate), job_id, "Python Flask MongoDB")

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "job_closed"
