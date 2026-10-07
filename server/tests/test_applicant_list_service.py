"""Employer applicant-list and workflow rules that the P1.0 grid depends on:
server-side pagination, score filtering/sorting, bulk transitions, and notes.

Driven by in-memory repository fakes — the fakes page and filter in Python but
hold the same method signatures as the real aggregates.
"""
from datetime import timedelta

from bson import ObjectId
import pytest

from app.services.application_service import ApplicationService
from app.utils.errors import ConflictError, ForbiddenError
from app.utils.time import utcnow
from tests.fakes import (
    FakeApplicationRepository,
    FakeCVRepository,
    FakeJobRepository,
    FakeMatchResultRepository,
    FakeUserRepository,
)


def build(*, applicants=3, statuses=None):
    """A job with N applications, one candidate user each, deterministic scores.

    Timestamps step by a minute per applicant so ordering assertions test the
    sort rather than the order two ``utcnow()`` calls happened to land in.
    """
    employer_id = ObjectId()
    job = {
        "_id": ObjectId(),
        "employerId": employer_id,
        "title": "Backend Engineer",
        "status": "open",
        "createdAt": utcnow(),
    }
    applications_repo = FakeApplicationRepository()
    users = [
        {"_id": employer_id, "name": "Rowan Ellis", "email": "rowan@northwind.example"},
    ] + [
        {"_id": ObjectId(), "name": f"Candidate {index}", "email": f"c{index}@test.dev"}
        for index in range(applicants)
    ]
    applications = []
    for index, user in enumerate(users[1:]):
        status = (statuses or {}).get(index, "submitted")
        submitted_at = utcnow() - timedelta(minutes=index)
        application = {
            "_id": ObjectId(),
            "jobId": job["_id"],
            "candidateId": user["_id"],
            "cvFileRef": ObjectId(),
            "cvParsedText": "Python",
            "status": status,
            "notes": [],
            "submittedAt": submitted_at,
            "createdAt": submitted_at,
            "updatedAt": submitted_at,
        }
        applications.append(application)
        applications_repo._store.insert(application)
        # Descending scores so sort assertions are unambiguous.
        applications_repo.set_score(str(application["_id"]), 90 - index * 10)

    service = ApplicationService(
        applications=applications_repo,
        jobs=FakeJobRepository([job]),
        cvs=FakeCVRepository(),
        match_results=FakeMatchResultRepository(),
        users=FakeUserRepository(users),
        db=None,
    )
    return service, job, applications_repo, applications, str(employer_id)


def test_list_paginates_and_reports_the_total():
    service, job, _, applications, employer_id = build(applicants=5)

    page, total = service.list_for_job(str(job["_id"]), employer_id, page=1, page_size=2)
    second, _ = service.list_for_job(str(job["_id"]), employer_id, page=2, page_size=2)

    assert total == 5
    assert [a["_id"] for a in page] == [a["_id"] for a in applications[:2]]
    assert [a["_id"] for a in second] == [a["_id"] for a in applications[2:4]]


def test_list_sorts_by_score_descending_and_ascending():
    service, job, _, applications, employer_id = build(applicants=4)

    high, _ = service.list_for_job(str(job["_id"]), employer_id, sort="score-desc", page_size=10)
    low, _ = service.list_for_job(str(job["_id"]), employer_id, sort="score-asc", page_size=10)

    assert high[0]["_id"] == applications[0]["_id"]
    assert low[0]["_id"] == applications[-1]["_id"]


def test_list_filters_by_status_and_minimum_score():
    service, job, _, applications, employer_id = build(
        applicants=4, statuses={1: "under_review", 2: "under_review"}
    )

    under_review, total = service.list_for_job(
        str(job["_id"]), employer_id, status="under_review", page_size=10
    )
    strong, _ = service.list_for_job(str(job["_id"]), employer_id, min_score=75, page_size=10)

    assert total == 2
    assert {a["_id"] for a in under_review} == {applications[1]["_id"], applications[2]["_id"]}
    # Scores are 90, 80, 70, 60 — min_score=75 keeps the first two.
    assert {a["_id"] for a in strong} == {applications[0]["_id"], applications[1]["_id"]}


def test_list_attaches_the_candidate_snapshot():
    service, job, _, applications, employer_id = build(applicants=1)

    rows, _ = service.list_for_job(str(job["_id"]), employer_id)

    assert rows[0]["candidate"]["name"] == "Candidate 0"


def test_foreign_employer_cannot_list_applicants():
    service, job, _, _, _ = build(applicants=1)

    with pytest.raises(ForbiddenError):
        service.list_for_job(str(job["_id"]), str(ObjectId()))


def test_bulk_move_reports_moved_and_skipped():
    service, job, _, applications, employer_id = build(
        applicants=3, statuses={2: "rejected"}
    )

    result = service.bulk_update_status(
        [str(a["_id"]) for a in applications], employer_id, "shortlisted"
    )

    assert result["updated"] == 2
    assert result["skipped"] == [{"id": str(applications[2]["_id"]), "reason": "cannot move from 'rejected'"}]


def test_bulk_move_rejects_ids_from_another_employer():
    service, job, _, applications, employer_id = build(applicants=1)

    result = service.bulk_update_status(
        [str(applications[0]["_id"]), str(ObjectId())], employer_id, "shortlisted"
    )

    assert result["updated"] == 1
    assert result["skipped"] == [{"id": str(ObjectId()), "reason": "not_found"}] or result["skipped"][0]["reason"] == "not_found"


def test_bulk_move_conflicts_when_nothing_can_move():
    service, job, _, applications, employer_id = build(applicants=2, statuses={0: "rejected", 1: "rejected"})

    with pytest.raises(ConflictError) as excinfo:
        service.bulk_update_status([str(a["_id"]) for a in applications], employer_id, "shortlisted")
    assert excinfo.value.code == "invalid_transition"


def test_bulk_move_stores_the_rejection_reason():
    service, job, _, applications, employer_id = build(applicants=1)

    service.bulk_update_status(
        [str(applications[0]["_id"])], employer_id, "rejected", "Not enough backend depth"
    )

    stored = service._applications.find_by_id(str(applications[0]["_id"]))
    assert stored["rejectionReason"] == "Not enough backend depth"


def test_status_update_keeps_the_grid_row_complete():
    """The employer grid renders candidate/score/company, so a status PATCH must
    return them or an optimistic update blanks the row."""
    service, job, _, applications, employer_id = build(applicants=1)

    updated = service.update_status(str(applications[0]["_id"]), employer_id, "under_review")

    assert updated["status"] == "under_review"
    assert updated["candidate"]["name"] == "Candidate 0"


def test_notes_are_capped_per_application():
    from app.schemas.application import MAX_NOTES

    service, job, _, applications, employer_id = build(applicants=1)
    application_id = str(applications[0]["_id"])
    for index in range(MAX_NOTES):
        service.add_note(application_id, employer_id, f"Note {index}")

    with pytest.raises(ConflictError) as excinfo:
        service.add_note(application_id, employer_id, "One too many")
    assert excinfo.value.code == "notes_limit_reached"


def test_adding_a_note_snapshots_the_author_name():
    service, job, _, applications, employer_id = build(applicants=1)

    notes = service.add_note(str(applications[0]["_id"]), employer_id, "Phone screen went well")

    assert notes[-1]["authorName"] == "Rowan Ellis"
    assert notes[-1]["body"] == "Phone screen went well"


def test_candidate_withdraw_is_own_application_only():
    service, job, _, applications, _ = build(applicants=1)
    candidate_id = str(applications[0]["candidateId"])

    with pytest.raises(ForbiddenError):
        service.withdraw(str(applications[0]["_id"]), str(ObjectId()))

    withdrawn = service.withdraw(str(applications[0]["_id"]), candidate_id)
    assert withdrawn["status"] == "withdrawn"


def test_withdrawing_an_already_rejected_application_conflicts():
    service, job, _, applications, _ = build(applicants=1, statuses={0: "rejected"})
    candidate_id = str(applications[0]["candidateId"])

    with pytest.raises(ConflictError) as excinfo:
        service.withdraw(str(applications[0]["_id"]), candidate_id)
    assert excinfo.value.code == "invalid_transition"
