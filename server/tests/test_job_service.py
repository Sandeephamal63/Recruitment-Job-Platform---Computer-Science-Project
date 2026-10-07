"""Job service pagination, employer joins, and dashboard stats."""
from bson import ObjectId
from datetime import timedelta

import pytest

from app.services.job_service import JobService
from app.utils.errors import ForbiddenError, NotFoundError
from app.utils.time import end_of_day, utc_today, utcnow
from tests.fakes import (
    FakeApplicationRepository,
    FakeJobRepository,
    FakeMatchResultRepository,
    FakeUserRepository,
)


def build_jobs(*, employer_jobs=2, candidate_jobs=0):
    """Employer has N open jobs; candidate sees only those N (no cross-leak)."""
    employer_id = ObjectId()
    employer_user = {"_id": employer_id, "name": "Rowan Ellis", "email": "r@northwind.example", "companyName": "Northwind"}
    jobs = []
    for index in range(employer_jobs):
        jobs.append(
            {
                "_id": ObjectId(),
                "employerId": employer_id,
                "title": f"Backend Engineer {index}",
                "status": "open",
                "createdAt": utcnow() - timedelta(days=index),
                "requiredSkills": ["Python"],
            }
        )
    other_employer_id = ObjectId()
    for index in range(candidate_jobs):
        jobs.append(
            {
                "_id": ObjectId(),
                "employerId": other_employer_id,
                "title": f"Foreign Job {index}",
                "status": "open",
                "createdAt": utcnow(),
                "requiredSkills": ["Go"],
            }
        )

    job_repo = FakeJobRepository(jobs)
    service = JobService(
        jobs=job_repo,
        users=FakeUserRepository([employer_user]),
        applications=FakeApplicationRepository(),
        match_results=FakeMatchResultRepository(),
    )
    # Return the repo's internal docs (which are copies) so tests can mutate them.
    repo_jobs = job_repo._store._docs
    return service, str(employer_id), repo_jobs


def test_browse_paginates_and_joins_employer():
    service, employer_id, _ = build_jobs(employer_jobs=5)

    jobs, total = service.list_open_jobs({"page": 1, "pageSize": 2, "sort": "newest"})
    second, _ = service.list_open_jobs({"page": 2, "pageSize": 2, "sort": "newest"})

    assert total == 5
    assert len(jobs) == 2
    assert len(second) == 2
    for job in jobs:
        assert "employer" in job
        assert job["employer"]["companyName"] == "Northwind"


def test_browse_shows_all_employers_jobs():
    """Public browse is a shared marketplace — every employer's open jobs are visible."""
    service, _, _ = build_jobs(employer_jobs=3, candidate_jobs=3)

    jobs, total = service.list_open_jobs({"page": 1, "pageSize": 10})

    assert total == 6
    assert len(jobs) == 6


def test_browse_sorts_by_title():
    service, _, _ = build_jobs(employer_jobs=3)

    jobs, _ = service.list_open_jobs({"page": 1, "pageSize": 10, "sort": "title"})

    titles = [job["title"] for job in jobs]
    assert titles == sorted(titles)


def test_browse_filters_location_employment_level_remote_and_salary():
    service, _, jobs = build_jobs(employer_jobs=4)
    # Mutate the in-memory repo's docs to carry the filterable fields.
    for i, job in enumerate(jobs[:3]):
        job["location"] = "Manchester" if i % 2 == 0 else "London"
        job["employmentType"] = "full-time"
        job["experienceLevel"] = "mid" if i < 2 else "senior"
        job["remote"] = i % 2 == 0
        job["salaryMin"] = 60000
        job["salaryMax"] = 80000
        job["currency"] = "GBP"

    jobs, total = service.list_open_jobs(
        {"page": 1, "pageSize": 10, "location": "Manchester", "remote": True}
    )
    assert total == 2  # indices 0 and 2

    jobs, total = service.list_open_jobs(
        {"page": 1, "pageSize": 10, "experienceLevel": "senior"}
    )
    assert total == 1


def test_browse_skills_are_conjunctive():
    service, _, jobs = build_jobs(employer_jobs=2)
    jobs[0]["requiredSkills"] = ["Python", "Flask"]
    jobs[1]["requiredSkills"] = ["Python"]

    jobs, total = service.list_open_jobs(
        {"page": 1, "pageSize": 10, "skills": ["Python", "Flask"]}
    )
    assert total == 1


def test_employer_overview_counts_shortlisted_and_average_score():
    employer_id = ObjectId()
    employer_user = {"_id": employer_id, "name": "Rowan Ellis", "email": "r@northwind.example"}
    jobs = [
        {
            "_id": ObjectId(),
            "employerId": employer_id,
            "title": "Backend Engineer",
            "status": "open",
            "createdAt": utcnow(),
        },
        {
            "_id": ObjectId(),
            "employerId": employer_id,
            "title": "Frontend Engineer",
            "status": "closed",
            "createdAt": utcnow(),
        },
    ]
    applications = [
        # Job 0: 1 shortlisted, 1 rejected
        {"_id": ObjectId(), "jobId": jobs[0]["_id"], "candidateId": ObjectId(), "status": "shortlisted", "createdAt": utcnow()},
        {"_id": ObjectId(), "jobId": jobs[0]["_id"], "candidateId": ObjectId(), "status": "rejected", "createdAt": utcnow()},
        # Job 1 (closed): 1 submitted
        {"_id": ObjectId(), "jobId": jobs[1]["_id"], "candidateId": ObjectId(), "status": "submitted", "createdAt": utcnow()},
    ]
    repo = FakeApplicationRepository()
    for app in applications:
        repo._store.insert(app)
    repo.set_score(str(applications[0]["_id"]), 85)
    repo.set_score(str(applications[1]["_id"]), 45)

    service = JobService(
        jobs=FakeJobRepository(jobs),
        users=FakeUserRepository([employer_user]),
        applications=repo,
        match_results=FakeMatchResultRepository(),
    )

    overview = service.employer_overview(str(employer_id))

    assert overview["openJobs"] == 1
    assert overview["closedJobs"] == 1
    assert overview["totalApplicants"] == 3
    assert overview["shortlisted"] == 1
    assert overview["averageScore"] == 65.0


def test_funnel_per_job():
    employer_id = ObjectId()
    employer_user = {"_id": employer_id, "name": "Rowan Ellis", "email": "r@northwind.example"}
    job = {
        "_id": ObjectId(),
        "employerId": employer_id,
        "title": "Backend Engineer",
        "status": "open",
        "createdAt": utcnow(),
    }
    repo = FakeApplicationRepository()
    apps = []
    for i, status in enumerate(["submitted", "under_review", "shortlisted", "rejected"]):
        app = {
            "_id": ObjectId(),
            "jobId": job["_id"],
            "candidateId": ObjectId(),
            "status": status,
            "createdAt": utcnow(),
        }
        apps.append(app)
        repo._store.insert(app)
    repo.set_score(str(apps[0]["_id"]), 80)

    service = JobService(
        jobs=FakeJobRepository([job]),
        users=FakeUserRepository([employer_user]),
        applications=repo,
        match_results=FakeMatchResultRepository(),
    )

    funnel = service.funnel_for_employer(str(employer_id))

    assert len(funnel) == 1
    stages = funnel[0]["stages"]
    assert stages["total"] == 4
    assert stages["submitted"] == 1
    assert stages["underReview"] == 1
    assert stages["shortlisted"] == 1
    assert stages["rejected"] == 1


def test_foreign_employer_cannot_view_job():
    service, employer_id, _ = build_jobs(employer_jobs=1)

    with pytest.raises(ForbiddenError):
        service.get_job(str(service._jobs.find_by_employer(employer_id)[0]["_id"]), str(ObjectId()), "employer")


def test_update_job_invalidates_matches_on_skills_change():
    employer_id = ObjectId()
    employer_user = {"_id": employer_id, "name": "Rowan Ellis", "email": "r@northwind.example"}
    job = {
        "_id": ObjectId(),
        "employerId": employer_id,
        "title": "Backend Engineer",
        "requiredSkills": ["Python"],
        "status": "open",
        "createdAt": utcnow(),
    }
    repo = FakeApplicationRepository()
    app = {"_id": ObjectId(), "jobId": job["_id"], "candidateId": ObjectId(), "status": "submitted", "createdAt": utcnow()}
    repo._store.insert(app)
    repo.set_score(str(app["_id"]), 90)
    match_repo = FakeMatchResultRepository()
    match_repo.upsert_result(str(app["_id"]), {"matchScore": 90, "matchedSkills": ["Python"], "missingSkills": [], "recommendations": [], "modelVersion": "v1"})

    service = JobService(
        jobs=FakeJobRepository([job]),
        users=FakeUserRepository([employer_user]),
        applications=repo,
        match_results=match_repo,
    )

    # Change requiredSkills -> existing match should be reset to pending.
    updated = service.update_job(str(job["_id"]), str(employer_id), {"requiredSkills": ["Python", "Flask"]})

    # The placeholder row now has matchScore=None, modelVersion="pending"
    match = match_repo.find_by_application(str(app["_id"]))
    assert match["matchScore"] is None
    assert match["modelVersion"] == "pending"

def test_browse_and_recommender_exclude_the_same_expired_jobs():
    """The two set reads must agree on what is still live.

    They are separate code paths over the same corpus, and a deadline enforced in
    only one of them is a defect a user would feel rather than a test failure:
    a role that vanished from browse but kept showing up on the candidate's
    dashboard as a recommendation is a recommendation nobody can act on.
    """
    employer_id = ObjectId()
    employer_user = {"_id": employer_id, "name": "Rowan Ellis", "email": "r@northwind.example"}
    live = end_of_day(utc_today() + timedelta(days=10))
    lapsed = end_of_day(utc_today() - timedelta(days=1))
    jobs = [
        {"_id": ObjectId(), "employerId": employer_id, "title": "Live", "status": "open",
         "deadline": live, "createdAt": utcnow(), "requiredSkills": ["Python"]},
        {"_id": ObjectId(), "employerId": employer_id, "title": "Lapsed", "status": "open",
         "deadline": lapsed, "createdAt": utcnow(), "requiredSkills": ["Python"]},
        {"_id": ObjectId(), "employerId": employer_id, "title": "No deadline", "status": "open",
         "createdAt": utcnow(), "requiredSkills": ["Python"]},
        {"_id": ObjectId(), "employerId": employer_id, "title": "Closed early", "status": "closed",
         "deadline": live, "createdAt": utcnow(), "requiredSkills": ["Python"]},
    ]
    service = JobService(
        jobs=FakeJobRepository(jobs),
        users=FakeUserRepository([employer_user]),
        applications=FakeApplicationRepository(),
        match_results=FakeMatchResultRepository(),
    )

    browsed, total = service.list_open_jobs({"page": 1, "pageSize": 10, "sort": "newest"})
    recommended = service._jobs.find_open_with_embeddings()

    assert total == 2
    assert sorted(j["title"] for j in browsed) == ["Live", "No deadline"]
    assert sorted(j["title"] for j in recommended) == ["Live", "No deadline"]


def test_browse_text_search_still_works_alongside_the_expiry_clause():
    """The text search is nested under ``$and`` so it cannot replace the
    top-level expiry ``$or`` that the repository owns. Regressing to a
    top-level ``$or`` would drop expiry from browse with no error anywhere."""
    employer_id = ObjectId()
    employer_user = {"_id": employer_id, "name": "Rowan Ellis", "email": "r@northwind.example"}
    jobs = [
        {"_id": ObjectId(), "employerId": employer_id, "title": "Rust Engineer",
         "description": "Systems work", "status": "open", "createdAt": utcnow()},
        {"_id": ObjectId(), "employerId": employer_id, "title": "Expired Rust Engineer",
         "description": "Systems work", "status": "open", "createdAt": utcnow(),
         "deadline": end_of_day(utc_today() - timedelta(days=1))},
    ]
    service = JobService(
        jobs=FakeJobRepository(jobs),
        users=FakeUserRepository([employer_user]),
        applications=FakeApplicationRepository(),
        match_results=FakeMatchResultRepository(),
    )

    found, total = service.list_open_jobs({"q": "Rust", "page": 1, "pageSize": 10})

    assert total == 1
    assert found[0]["title"] == "Rust Engineer"


def test_deadline_edit_does_not_re_encode_the_job_embedding():
    """``deadline`` is deliberately not in ``EMBEDDED_FIELDS``.

    It is not part of the text an embedding is built from, so changing it must
    not make the employer pay for a model call. The same reasoning that keeps
    re-embedding rare is what would quietly become a per-save cost if the
    deadline edit were added to the embedded set.
    """
    from app.services.job_service import _embedding_is_stale

    job = {
        "_id": ObjectId(),
        "title": "Backend Engineer",
        "description": "Python APIs",
        "requiredSkills": ["Python"],
        "status": "open",
        "createdAt": utcnow(),
    }

    assert _embedding_is_stale(job, {"deadline": end_of_day(utc_today())}) is False
    assert _embedding_is_stale(job, {"deadline": None}) is False
    # The fields that *are* embedded still trigger it.
    assert _embedding_is_stale(job, {"title": "Renamed"}) is True
    assert _embedding_is_stale(job, {"description": "Rewritten"}) is True
    assert _embedding_is_stale(job, {"requiredSkills": ["Python", "Go"]}) is True
    # As do non-embedded commercial fields, which are also not part of the text.
    assert _embedding_is_stale(job, {"salaryMin": 90000}) is False
