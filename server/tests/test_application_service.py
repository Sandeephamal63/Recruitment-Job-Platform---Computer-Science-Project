"""Application service rules at the service layer (status funnel, ownership,
reading) driven by in-memory repository fakes — no Mongo involved."""
from bson import ObjectId
import pytest

from app.services.application_service import ApplicationService
from app.utils.errors import ConflictError, ForbiddenError, NotFoundError
from app.utils.time import utcnow
from tests.fakes import (
    FakeApplicationRepository,
    FakeCVRepository,
    FakeJobRepository,
    FakeMatchResultRepository,
    FakeUserRepository,
)


def make_service(*, applications=None, jobs=None, users=None, matches=None):
    return ApplicationService(
        applications=FakeApplicationRepository(applications),
        jobs=FakeJobRepository(jobs),
        cvs=FakeCVRepository(),
        match_results=FakeMatchResultRepository(matches),
        users=FakeUserRepository(users),
        db=None,
    )


def seeded_docs():
    employer_id = ObjectId()
    candidate_id = ObjectId()
    job = {
        "_id": ObjectId(),
        "employerId": employer_id,
        "title": "Backend Engineer",
        "description": "APIs",
        "requiredSkills": ["Python"],
        "status": "open",
    }
    application = {
        "_id": ObjectId(),
        "jobId": job["_id"],
        "candidateId": candidate_id,
        "cvFileRef": ObjectId(),
        "cvParsedText": "Python",
        "status": "submitted",
        "submittedAt": utcnow(),
        "createdAt": utcnow(),
        "updatedAt": utcnow(),
    }
    return application, job, employer_id, candidate_id


def test_update_status_advances_through_funnel():
    application, job, employer_id, _ = seeded_docs()
    service = make_service(applications=[application], jobs=[job])

    result = service.update_status(str(application["_id"]), str(employer_id), "under_review")
    assert result["status"] == "under_review"

    result = service.update_status(str(application["_id"]), str(employer_id), "shortlisted")
    assert result["status"] == "shortlisted"


def test_rejected_is_terminal():
    application, job, employer_id, _ = seeded_docs()
    application["status"] = "rejected"
    service = make_service(applications=[application], jobs=[job])

    with pytest.raises(ConflictError) as excinfo:
        service.update_status(str(application["_id"]), str(employer_id), "under_review")
    assert excinfo.value.code == "invalid_transition"


def test_backwards_transition_conflicts():
    application, job, employer_id, _ = seeded_docs()
    application["status"] = "shortlisted"
    service = make_service(applications=[application], jobs=[job])

    with pytest.raises(ConflictError) as excinfo:
        service.update_status(str(application["_id"]), str(employer_id), "under_review")
    assert excinfo.value.code == "invalid_transition"


def test_same_status_is_idempotent_noop():
    application, job, employer_id, _ = seeded_docs()
    application["status"] = "under_review"
    service = make_service(applications=[application], jobs=[job])

    result = service.update_status(str(application["_id"]), str(employer_id), "under_review")
    assert result["status"] == "under_review"


def test_foreign_employer_cannot_update_status():
    application, job, _, _ = seeded_docs()
    other_employer = ObjectId()
    service = make_service(applications=[application], jobs=[job])

    with pytest.raises(ForbiddenError):
        service.update_status(str(application["_id"]), str(other_employer), "shortlisted")


def test_missing_application_not_found():
    _, job, employer_id, _ = seeded_docs()
    service = make_service(jobs=[job])

    with pytest.raises(NotFoundError) as excinfo:
        service.update_status(str(ObjectId()), str(employer_id), "shortlisted")
    assert excinfo.value.code == "application_not_found"


def test_get_application_candidate_ownership():
    application, job, _, candidate_id = seeded_docs()
    service = make_service(applications=[application], jobs=[job])

    result = service.get_application(str(application["_id"]), str(candidate_id), "candidate")
    assert str(result["_id"]) == str(application["_id"])
    assert result["job"]["title"] == "Backend Engineer"

    other_candidate = ObjectId()
    with pytest.raises(ForbiddenError):
        service.get_application(str(application["_id"]), str(other_candidate), "candidate")


def test_get_application_employer_requires_ownership():
    application, job, employer_id, candidate_id = seeded_docs()
    user = {"_id": application["candidateId"], "name": "Eva", "email": "eva@test.dev"}
    match = {
        "applicationId": application["_id"],
        "matchScore": 84,
        "matchedSkills": ["Python"],
        "missingSkills": [],
        "recommendations": ["nice"],
        "modelVersion": "spacy-en_core_web_sm-st-all-MiniLM-L6-v2",
        "createdAt": utcnow(),
    }
    service = make_service(
        applications=[application],
        jobs=[job],
        users=[user],
        matches=[match],
    )

    result = service.get_application(str(application["_id"]), str(employer_id), "employer")
    assert str(result["candidate"]["id"]) == str(candidate_id)
    assert result["candidate"]["name"] == "Eva"
    assert result["match"]["matchScore"] == 84

    foreign_employer = ObjectId()
    with pytest.raises(ForbiddenError):
        service.get_application(str(application["_id"]), str(foreign_employer), "employer")


def test_counts_for_employer_only_own_jobs():
    _, job, employer_id, _ = seeded_docs()
    other_job = {"_id": ObjectId(), "employerId": ObjectId(), "title": "Other", "status": "open"}
    application = {
        "_id": ObjectId(),
        "jobId": job["_id"],
        "candidateId": ObjectId(),
        "cvParsedText": "Python",
        "status": "submitted",
        "createdAt": utcnow(),
        "updatedAt": utcnow(),
        "submittedAt": utcnow(),
    }
    applications = FakeApplicationRepository([application])
    jobs = FakeJobRepository([job, other_job])
    service = ApplicationService(applications, jobs, FakeCVRepository(), FakeMatchResultRepository([]), FakeUserRepository([]), db=None)

    counts = service.counts_for_employer(str(employer_id))
    assert counts == [{"jobId": str(job["_id"]), "count": 1}]


def employer_user(employer_id):
    return {
        "_id": employer_id,
        "name": "Rowan Ellis",
        "email": "rowan@northwind.example",
        "companyName": "Northwind",
        "companySize": "51-200",
        "companyIndustry": "Software",
        "logoFileRef": ObjectId(),
    }


def test_candidate_list_attaches_the_company():
    """The candidate's own list is the one place they learn who they applied to,
    and it used to carry no employer at all — the client rendered a hardcoded
    'Unknown Company' because neither ``job.employer`` nor ``employer`` existed
    on the wire."""
    application, job, employer_id, candidate_id = seeded_docs()
    service = make_service(
        applications=[application],
        jobs=[job],
        users=[employer_user(employer_id)],
    )

    rows = service.list_candidate_applications(str(candidate_id))

    assert len(rows) == 1
    assert rows[0]["employerId"] == str(employer_id)
    assert rows[0]["employer"]["companyName"] == "Northwind"
    assert rows[0]["employer"]["companyLogoUrl"] == f"profile/employers/{employer_id}/logo"


def test_candidate_read_of_an_application_gets_the_company():
    application, job, employer_id, candidate_id = seeded_docs()
    service = make_service(
        applications=[application],
        jobs=[job],
        users=[employer_user(employer_id)],
    )

    result = service.get_application(str(application["_id"]), str(candidate_id), "candidate")

    assert result["employer"]["companyName"] == "Northwind"
    assert result["employer"]["companySize"] == "51-200"


def test_candidate_read_of_an_application_gets_the_match_score():
    """The score is the whole reason the pipeline runs, and it is shown to both
    sides — the candidate's application detail renders the same report the
    employer sees, so the number has to be on the candidate's payload too."""
    application, job, employer_id, candidate_id = seeded_docs()
    match = {
        "applicationId": application["_id"],
        "matchScore": 84,
        "matchedSkills": ["Python"],
        "missingSkills": [],
        "recommendations": [],
        "modelVersion": "spacy-en_core_web_sm-st-all-MiniLM-L6-v2",
        "createdAt": utcnow(),
    }
    service = make_service(
        applications=[application],
        jobs=[job],
        users=[employer_user(employer_id)],
        matches=[match],
    )

    result = service.get_application(str(application["_id"]), str(candidate_id), "candidate")

    assert result["match"]["matchScore"] == 84


def test_candidate_never_sees_employer_review_notes():
    """Review notes are the employer's private working notes. The note routes
    are employer-only; this asserts the same holds for a candidate reading the
    application payload they own."""
    application, job, employer_id, candidate_id = seeded_docs()
    application["notes"] = [
        {
            "id": ObjectId(),
            "body": "Salary expectations too high",
            "authorUserId": employer_id,
            "authorName": "Rowan Ellis",
            "createdAt": utcnow(),
        }
    ]
    service = make_service(
        applications=[application],
        jobs=[job],
        users=[employer_user(employer_id)],
    )

    candidate_view = service.get_application(str(application["_id"]), str(candidate_id), "candidate")
    assert "notes" not in candidate_view

    employer_view = service.get_application(str(application["_id"]), str(employer_id), "employer")
    assert [note["body"] for note in employer_view["notes"]] == ["Salary expectations too high"]
