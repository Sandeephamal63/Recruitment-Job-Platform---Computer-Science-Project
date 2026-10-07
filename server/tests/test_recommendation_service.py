"""Tests for the proactive candidate recommender.

Three things are load-bearing and therefore covered here:

* the scoring function ranks and blends correctly, and agrees with the
  per-application scorer on the same text pair (a dashboard score that
  disagreed with the post-application score would be a visible product bug);
* the cache is reused when fresh and recomputed when the candidate's profile
  has moved on;
* the endpoint is candidate-only.
"""

from datetime import timedelta

import pytest
from bson import ObjectId

from app.repositories.job_repository import JobRepository
from app.repositories.user_repository import UserRepository
from app.services.matching_service import (
    MODEL_VERSION_EMBEDDING,
    MODEL_VERSION_TFIDF,
    embed_text,
    job_embedding,
    score_candidate_against_jobs,
    score_cv,
)
from app.services.recommendation_service import (
    RecommendationService,
    is_fresh,
    profile_text,
)
from app.utils.errors import ForbiddenError
from app.utils.time import utcnow
from tests.fakes import (
    FakeCandidateRecommendationRepository,
    FakeJobRepository,
    FakeUserRepository,
)

REPO_JOB_ID = str(ObjectId())


class StaticEmbedder:
    """Returns a fixed vector per input, so cosines are exact and model-free.

    A job whose text mentions the needle token shares the candidate's vector and
    therefore scores a perfect cosine; any other job is orthogonal to it.
    """

    NEEDLE = "needle"

    def encode(self, texts, normalize_embeddings=True):
        vectors = []
        for text in texts:
            if self.NEEDLE in text:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return vectors


def make_job(skills, *, related=False, status="open", title="Engineer"):
    """A job posting whose text either does or does not overlap the embedder's
    needle token, so a test can ask for a high or a low semantic score."""
    return {
        "_id": ObjectId(),
        "title": f"{title} {StaticEmbedder.NEEDLE}" if related else title,
        "description": (
            f"Work on {StaticEmbedder.NEEDLE} systems" if related else "Work on software"
        ),
        "requiredSkills": list(skills),
        "status": status,
    }


def identity(text):
    """Stands in for the spaCy lemmatiser so no test loads a model."""
    return text


def embed_posting(posting, embedder):
    """Stamp a posting with its vector the way ``JobService.create_job`` does."""
    posting["embedding"] = job_embedding(posting, embedder=embedder, preprocess=identity)
    posting["embeddingModel"] = MODEL_VERSION_EMBEDDING
    return posting


def make_candidate(*, role="candidate", skills=None, cv_text=None, **extra):
    doc = {
        "_id": ObjectId(),
        "role": role,
        "name": "Test Candidate",
        "email": "candidate@test.dev",
        "headline": "Backend engineer",
        "skills": list(skills or []),
        "cvParsedText": cv_text,
        "createdAt": utcnow(),
    }
    doc.update(extra)
    return doc


class StubJobService:
    """Stands in for the real JobService, whose only contribution here is the
    public employer join this service reuses rather than re-implements."""

    def enrich_with_employers(self, jobs):
        for entry in jobs:
            entry["employer"] = {"companyName": "Northwind"}


def build_service(users=None, jobs=None, cached=None):
    return RecommendationService(
        FakeJobRepository(jobs or []),
        FakeUserRepository(users or [make_candidate()]),
        FakeCandidateRecommendationRepository(cached or []),
        StubJobService(),
    )


def cached_row(candidate_id, *, job_id="cached-job", score=91, computed_at=None):
    return {
        "candidateId": str(candidate_id),
        "recommendations": [{"jobId": job_id, "matchScore": score}],
        "computedAt": computed_at or utcnow(),
    }


# --- scoring -----------------------------------------------------------------


def test_ranks_jobs_by_match_score_descending():
    embedder = StaticEmbedder()
    strong = embed_posting(make_job(["python"], related=True), embedder)
    weak = embed_posting(make_job(["python"]), embedder)
    rows = score_candidate_against_jobs(
        "python",
        [weak, strong],
        profile_embedding=[1.0, 0.0],
        embedder=embedder,
        preprocess=identity,
        limit=10,
    )
    assert [row["matchScore"] for row in rows] == sorted(
        (row["matchScore"] for row in rows), reverse=True
    )
    assert rows[0]["jobId"] == str(strong["_id"])


def test_score_is_built_from_the_shared_blend():
    """A perfect cosine plus full skill overlap must land on the same 100 the
    per-application scorer produces for the same text pair."""
    embedder = StaticEmbedder()
    strong = embed_posting(make_job(["python"], related=True), embedder)
    rows = score_candidate_against_jobs(
        "python needle",
        [strong],
        profile_embedding=[1.0, 0.0],
        embedder=embedder,
        preprocess=identity,
        limit=10,
    )
    assert rows[0]["matchScore"] == score_cv(
        "python needle", strong, embedder=embedder, preprocess=identity
    )["matchScore"]


def test_dashboard_and_post_application_scores_agree():
    """The invariant the whole design rests on: a score computed on the fly
    against a freshly encoded CV must equal the same score computed from stored
    vectors. If a pooling or preprocessing change ever broke that equivalence,
    the dashboard would contradict the employer's own view of the application."""
    embedder = StaticEmbedder()
    cv_text = "python needle"
    postings = [
        embed_posting(make_job(["python"]), embedder),
        embed_posting(make_job(["python", "docker"], related=True), embedder),
    ]
    profile_vector = embed_text(cv_text, embedder, identity)

    proactive = {
        row["jobId"]: row["matchScore"]
        for row in score_candidate_against_jobs(
            cv_text,
            postings,
            profile_embedding=profile_vector,
            embedder=embedder,
            preprocess=identity,
            limit=10,
        )
    }
    reactive = {
        str(posting["_id"]): score_cv(
            cv_text, posting, embedder=embedder, preprocess=identity
        )["matchScore"]
        for posting in postings
    }
    assert proactive == reactive


def test_missing_stored_vector_falls_back_instead_of_dropping_the_job():
    """A job written before embeddings existed still ranks, on TF-IDF."""
    unembedded = make_job(["python"], title="No vector")
    rows = score_candidate_against_jobs(
        "python needle",
        [unembedded],
        profile_embedding=[1.0, 0.0],
        embedder=StaticEmbedder(),
        preprocess=identity,
        limit=10,
    )
    assert len(rows) == 1
    assert rows[0]["modelVersion"] == MODEL_VERSION_TFIDF
    assert 0 <= rows[0]["matchScore"] <= 100


def test_job_vector_from_a_different_model_is_refused():
    """A vector stored by a previous model must not be compared to a current one.

    A dot product between two unrelated vector spaces returns a plausible number
    in the 0-1 range, not an error, so the failure would be invisible on a
    partially backfilled corpus. Refusing the pair and falling back to TF-IDF is
    what makes a model migration safe to run before the backfill finishes.
    """
    embedder = StaticEmbedder()
    posting = embed_posting(make_job(["python"]), embedder)
    posting["embeddingModel"] = "some-previous-model-v1"

    rows = score_candidate_against_jobs(
        "python needle",
        [posting],
        profile_embedding=[1.0, 0.0],
        embedder=embedder,
        preprocess=identity,
        limit=10,
    )
    assert rows[0]["modelVersion"] == MODEL_VERSION_TFIDF
    assert 0 <= rows[0]["matchScore"] <= 100


def test_rows_carry_the_documented_shape():
    embedder = StaticEmbedder()
    rows = score_candidate_against_jobs(
        "python",
        [embed_posting(make_job(["python", "kubernetes"]), embedder)],
        profile_embedding=[1.0, 0.0],
        embedder=embedder,
        preprocess=identity,
        limit=10,
    )
    assert set(rows[0]) == {
        "jobId",
        "matchScore",
        "matchedSkills",
        "missingSkills",
        "recommendations",
        "modelVersion",
    }
    assert rows[0]["modelVersion"] == MODEL_VERSION_EMBEDDING
    assert rows[0]["matchedSkills"] == ["python"]
    assert rows[0]["missingSkills"] == ["kubernetes"]
    assert rows[0]["recommendations"]


def test_limit_truncates_the_ranking():
    embedder = StaticEmbedder()
    postings = [
        embed_posting(make_job(["python"], title=f"Role {index}"), embedder)
        for index in range(5)
    ]
    rows = score_candidate_against_jobs(
        "python needle",
        postings,
        profile_embedding=[1.0, 0.0],
        embedder=embedder,
        preprocess=identity,
        limit=2,
    )
    assert len(rows) == 2


def test_score_stays_within_bounds():
    rows = score_candidate_against_jobs(
        "python", [make_job(["python"])], embedder=StaticEmbedder(), limit=10
    )
    assert 0 <= rows[0]["matchScore"] <= 100


def test_employer_role_is_refused():
    employer = make_candidate(role="employer")
    service = build_service(users=[employer])
    with pytest.raises(ForbiddenError):
        service.recommendations_for_candidate(str(employer["_id"]))


# --- cache freshness ---------------------------------------------------------


def test_is_fresh_when_computed_at_or_after_the_profile_stamp():
    now = utcnow()
    assert is_fresh(now, now) is True
    assert is_fresh(now, now - timedelta(seconds=1)) is True
    assert is_fresh(now - timedelta(seconds=1), now) is False


def test_missing_stamps_are_never_fresh():
    assert is_fresh(None, utcnow()) is False
    assert is_fresh(utcnow(), None) is False
    assert is_fresh(None, None) is False


def test_fresh_cache_is_returned_without_recomputing():
    profile = make_candidate(profileUpdatedAt=utcnow() - timedelta(minutes=5))
    service = build_service(
        users=[profile],
        jobs=[make_job(["python"])],
        cached=[cached_row(profile["_id"])],
    )
    payload = service.recommendations_for_candidate(str(profile["_id"]))
    assert [row["jobId"] for row in payload["recommendations"]] == ["cached-job"]


def test_profile_edit_makes_the_cache_stale():
    profile = make_candidate(profileUpdatedAt=utcnow())
    service = build_service(
        users=[profile],
        jobs=[make_job(["python"])],
        cached=[
            cached_row(profile["_id"], job_id="stale-job", computed_at=utcnow() - timedelta(hours=1))
        ],
    )
    payload = service.recommendations_for_candidate(str(profile["_id"]))
    assert [row["jobId"] for row in payload["recommendations"]] != ["stale-job"]


def test_legacy_user_without_a_stamp_falls_back_to_created_at():
    """A document written before ``profileUpdatedAt`` existed still resolves to a
    real stamp rather than being permanently stale."""
    profile = make_candidate(createdAt=utcnow() - timedelta(hours=2))
    profile.pop("profileUpdatedAt", None)
    service = build_service(
        users=[profile],
        jobs=[],
        cached=[
            cached_row(
                profile["_id"], computed_at=utcnow() - timedelta(hours=1)
            )
        ],
    )
    payload = service.recommendations_for_candidate(str(profile["_id"]))
    assert [row["jobId"] for row in payload["recommendations"]] == ["cached-job"]


def test_computed_result_is_cached_for_the_next_read():
    profile = make_candidate(profileUpdatedAt=utcnow() - timedelta(minutes=1))
    service = build_service(users=[profile], jobs=[make_job(["python"])])
    candidate_id = str(profile["_id"])

    first = service.recommendations_for_candidate(candidate_id)
    assert first["recommendations"]

    job_repo = service._jobs
    job_repo._store._docs = []
    second = service.recommendations_for_candidate(candidate_id)
    assert second["recommendations"] == first["recommendations"]


def test_recommendations_carry_the_presentation_fields():
    profile = make_candidate(profileUpdatedAt=utcnow() - timedelta(minutes=1))
    service = build_service(users=[profile], jobs=[make_job(["python"])])
    row = service.recommendations_for_candidate(str(profile["_id"]))["recommendations"][0]
    assert row["jobTitle"] == "Engineer"
    assert row["companyName"] == "Northwind"


def test_candidate_without_a_profile_text_gets_no_recommendations():
    """No CV and no skills means nothing to rank against; the emptiness is
    cached rather than rescanning the corpus on every load."""
    profile = make_candidate(skills=[], cv_text=None, headline="")
    service = build_service(users=[profile], jobs=[make_job(["python"])])
    payload = service.recommendations_for_candidate(str(profile["_id"]))
    assert payload["recommendations"] == []
    assert payload["computedAt"] is not None


def test_profile_text_prefers_the_cv_then_falls_back_to_skills():
    assert profile_text(make_candidate(cv_text="  full cv text  ")) == "full cv text"
    assert profile_text(make_candidate(headline="Dev", skills=["python"])) == "Dev python"


# --- repositories ------------------------------------------------------------


def test_repositories_expose_the_recommender_reads():
    """Guards the two repository methods the service depends on, so a rename
    cannot silently break the recommender's only Mongo access."""
    assert hasattr(JobRepository, "find_open_with_embeddings")
    assert hasattr(UserRepository, "find_profile_embedding")
