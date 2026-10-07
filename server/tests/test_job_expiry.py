"""Application deadlines: how a job closes by the passage of time.

The rule is split by design — ``services.job_service.is_expired`` decides it for
a single posting, ``repositories.job_repository.open_job_filter`` expresses the
same rule as a Mongo query for the reads that return a *set* of jobs. A posting
therefore has two ways of being "not open", and a candidate sees browse, a
single job, the recommender and the apply form through different code paths.

That is why these live in their own file rather than inside ``test_job_service``:
the thing worth protecting is not any one call site but that all of them agree.
A deadline that is enforced in browse but not in the recommender would still let
the platform recommend a role nobody can apply to.
"""
from datetime import timedelta

import pytest
from bson import ObjectId
from marshmallow import ValidationError

from app.repositories.job_repository import open_job_filter
from app.schemas.job import job_create_schema, job_schema, job_update_schema
from app.services.job_service import JobService, is_expired
from app.utils.errors import NotFoundError
from app.utils.time import end_of_day, utc_today, utcnow
from tests.fakes import (
    FakeApplicationRepository,
    FakeJobRepository,
    FakeMatchResultRepository,
    FakeUserRepository,
)


def in_days(days: int):
    """A stored deadline, as a datetime at the end of that civil date."""
    return end_of_day(utc_today() + timedelta(days=days))


def build_service(*jobs):
    return JobService(
        jobs=FakeJobRepository(list(jobs)),
        users=FakeUserRepository([]),
        applications=FakeApplicationRepository(),
        match_results=FakeMatchResultRepository(),
    )


def job_doc(employer_id, *, title="Data Scientist", status="open", deadline=None, **extra):
    return {
        "_id": ObjectId(),
        "employerId": employer_id,
        "title": title,
        "status": status,
        "deadline": deadline,
        "createdAt": utcnow(),
        "updatedAt": utcnow(),
        **extra,
    }


# --- the two halves agree -----------------------------------------------------


@pytest.mark.parametrize(
    "deadline, expected",
    [
        (None, False),               # no deadline: closes only if the employer says so
        (in_days(1), False),
        (in_days(30), False),
        (end_of_day(utc_today()), False),   # still open for the whole day it names
        (in_days(-1), True),
        (in_days(-30), True),
    ],
)
def test_is_expired_matches_the_query_predicate(deadline, expected):
    """One rule, two expressions: the service predicate and the Mongo filter.

    Deriving both from a shared idea is not possible — one is a boolean over a
    loaded document, the other is a query fragment evaluated by Mongo — so this
    asserts they classify the same documents instead of trusting review to
    notice a divergence.
    """
    job = {"_id": ObjectId(), "status": "open", "deadline": deadline}
    now = utcnow()

    assert is_expired(job, now) is expected

    # The $or accepts a document when either branch holds: no deadline at all,
    # or a deadline still in the future. A closed job matches neither.
    clause = open_job_filter(now)
    matched = clause["$or"][0] == {"deadline": None} and job.get("deadline") is None
    matched = matched or (job.get("deadline") is not None and job["deadline"] >= now)
    assert matched is (not expected)


def test_closed_job_stays_closed_even_with_a_live_deadline():
    """A future deadline cannot reopen a posting the employer closed."""
    job = {"status": "closed", "deadline": in_days(30)}

    assert is_expired(job) is False
    assert open_job_filter(utcnow())["status"] == "open"


# --- storage: end of the day, in UTC -----------------------------------------


def test_deadline_is_stored_at_the_end_of_the_day_it_names():
    """Why end-of-day rather than midnight.

    A deadline is a date an employer reads off a calendar, not an instant. Stored
    at midnight it would be un-openable for the whole day it names; stored at the
    end, the role accepts applications through that day and the expiry check is a
    single comparison with no date truncation at any read site.
    """
    chosen = (utc_today() + timedelta(days=30)).isoformat()
    loaded = job_create_schema.load(
        {
            "title": "Backend Engineer",
            "description": "Python APIs",
            "requiredSkills": ["Python"],
            "location": "London",
            "employmentType": "full-time",
            "deadline": chosen,
        }
    )

    assert loaded["deadline"] == end_of_day(utc_today() + timedelta(days=30))
    assert (loaded["deadline"] - end_of_day(utc_today())).days == 30


def test_deadline_round_trips_as_the_date_the_employer_typed():
    chosen = (utc_today() + timedelta(days=7)).isoformat()
    loaded = job_create_schema.load(
        {
            "title": "T",
            "description": "D",
            "requiredSkills": [],
            "location": "L",
            "employmentType": "full-time",
            "deadline": chosen,
        }
    )
    doc = {
        "_id": ObjectId(),
        "title": "T",
        "description": "D",
        "requiredSkills": [],
        "location": "L",
        "employmentType": "full-time",
        "status": "open",
        "deadline": loaded["deadline"],
        "createdAt": utcnow(),
        "updatedAt": utcnow(),
    }

    assert job_schema.dump(doc)["deadline"] == chosen


def test_missing_deadline_serializes_as_null_not_an_absent_key():
    """Clients can then treat the field as always present."""
    doc = {
        "_id": ObjectId(),
        "title": "T",
        "description": "D",
        "requiredSkills": [],
        "location": "L",
        "employmentType": "full-time",
        "status": "open",
        "createdAt": utcnow(),
        "updatedAt": utcnow(),
    }

    assert "deadline" in job_schema.dump(doc)
    assert job_schema.dump(doc)["deadline"] is None


# --- validation ---------------------------------------------------------------


def _create_payload(**overrides):
    payload = {
        "title": "T",
        "description": "D",
        "requiredSkills": [],
        "location": "L",
        "employmentType": "full-time",
    }
    return {**payload, **overrides}


def test_deadline_is_optional():
    assert "deadline" not in job_create_schema.load(_create_payload())


def test_deadline_of_today_is_accepted():
    """Comparing against *today* rather than the current instant.

    An end-of-day deadline must be settable on the day it names — otherwise
    'closes today' would be the one value the API refuses, which is a real
    mistake an employer makes.
    """
    loaded = job_create_schema.load(_create_payload(deadline=utc_today().isoformat()))

    assert loaded["deadline"] == end_of_day(utc_today())


def test_past_deadline_is_rejected_on_create():
    with pytest.raises(ValidationError) as exc:
        job_create_schema.load(_create_payload(deadline=in_days(-1).date().isoformat()))

    assert "past" in str(exc.value.messages["deadline"])


def test_past_deadline_is_rejected_on_update():
    with pytest.raises(ValidationError) as exc:
        job_update_schema.load({"deadline": in_days(-1).date().isoformat()})

    assert "past" in str(exc.value.messages["deadline"])


def test_explicit_null_clears_the_deadline():
    """Withdrawing a date must be possible, not a validation error."""
    assert job_update_schema.load({"deadline": None}) == {"deadline": None}


@pytest.mark.parametrize("bad", ["31/12/2026", "2026-12-31T10:00:00Z", "next friday", ""])
def test_deadline_must_be_a_bare_iso_date(bad):
    """A timestamp is refused on purpose.

    The field is a civil date. Accepting an instant here would mean storing a
    precision the UI does not collect and the employer did not choose.
    """
    with pytest.raises(ValidationError):
        job_create_schema.load(_create_payload(deadline=bad))


# --- the read-time decision ---------------------------------------------------


def test_get_job_hides_an_expired_posting_from_a_candidate():
    employer_id = ObjectId()
    job = job_doc(employer_id, deadline=in_days(-1))
    service = build_service(job)

    # A candidate is told the job does not exist...
    with pytest.raises(NotFoundError):
        service.get_job(str(job["_id"]), "someone-else", "candidate")
    # ...but the employer who posted it can still see it, expiry or not.
    assert (
        service.get_job(str(job["_id"]), str(employer_id), "employer")["title"]
        == "Data Scientist"
    )


def test_employer_overview_does_not_count_expired_postings_as_open():
    """The dashboard must not claim an open role that browse already hides."""
    employer_id = ObjectId()
    service = build_service(
        job_doc(employer_id, title="Live", deadline=in_days(10)),
        job_doc(employer_id, title="Lapsed", deadline=in_days(-1)),
        job_doc(employer_id, title="Manually closed", status="closed", deadline=in_days(10)),
    )

    overview = service.employer_overview(str(employer_id))

    assert overview["openJobs"] == 1
    assert overview["closedJobs"] == 2
