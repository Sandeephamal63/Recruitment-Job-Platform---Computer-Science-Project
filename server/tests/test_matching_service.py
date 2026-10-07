"""Match-score calculation unit tests (M6-mandated).

Model-free by design: ``score_cv`` accepts an injectable embedder/preprocess so
the blend, the gazetteer diff, and the TF-IDF fallback are tested without ever
loading spaCy or the sentence-transformers model — that keeps CI light and the
"swappable scorer" contract exercised deterministically.
"""
import numpy as np
import pytest

from app.services import matching_service as ms


class PerfectSimilarity:
    """Both texts embed to the same unit vector -> cosine 1 -> semantic 1.0."""

    def encode(self, texts, normalize_embeddings=True):
        return np.array([[1.0, 0.0]] * len(texts))


class OrthogonalSimilarity:
    """cv and job embeds are perpendicular -> cosine 0 -> semantic 0.5."""

    def encode(self, texts, normalize_embeddings=True):
        return np.array([[1.0, 0.0], [0.0, 1.0]])


class FailingEmbedder:
    """Simulates embedding-model unavailability to force the TF-IDF fallback."""

    def encode(self, texts, normalize_embeddings=True):
        raise RuntimeError("embedding model unavailable")


JOB = {"title": "Backend Engineer", "description": "APIs and services", "requiredSkills": ["Python", "Flask"]}


def score(cv_text, job=JOB, embedder=None):
    return ms.score_cv(cv_text, job, embedder=embedder, preprocess=lambda text: text)


def test_full_skill_overlap_and_semantic_match():
    result = score("Python and Flask expertise", embedder=PerfectSimilarity())
    assert result["matchScore"] == 100
    assert result["matchedSkills"] == ["Python", "Flask"]
    assert result["missingSkills"] == []
    assert result["modelVersion"] == ms.MODEL_VERSION_EMBEDDING


def test_partial_overlap_blended_with_semantic():
    job = {"requiredSkills": ["Python", "Kubernetes"]}
    # overlap 0.5 (Python matched), semantic 0.5 -> 0.5*0.5 + 0.5*0.5 = 0.5 -> 50
    result = score("Python", job=job, embedder=OrthogonalSimilarity())
    assert result["matchScore"] == 50
    assert result["matchedSkills"] == ["Python"]
    assert result["missingSkills"] == ["Kubernetes"]


def test_zero_overlap_rescued_by_semantic_only_halfway():
    job = {"requiredSkills": ["Ruby"]}
    # overlap 0, semantic 1 -> 0.5 -> 50
    result = score("Python and Flask", job=job, embedder=PerfectSimilarity())
    assert result["matchScore"] == 50
    assert result["missingSkills"] == ["Ruby"]


def test_no_required_skills_scores_pure_semantic():
    result = score("Any words at all", job={"title": "Generalist"}, embedder=OrthogonalSimilarity())
    assert result["matchScore"] == 50  # overlap is None -> semantic only


def test_empty_cv_scores_zero_with_all_skills_missing():
    result = score("", embedder=PerfectSimilarity())
    assert result["matchScore"] == 0
    assert result["matchedSkills"] == []
    assert result["missingSkills"] == ["Python", "Flask"]


def test_embedding_failure_falls_back_to_tfidf():
    result = score(
        "Python Flask Docker MongoDB",
        job={"requiredSkills": ["Python", "Flask", "Docker", "MongoDB"]},
        embedder=FailingEmbedder(),
    )
    assert result["modelVersion"] == ms.MODEL_VERSION_TFIDF
    assert result["matchScore"] >= 50  # full skill overlap alone floor
    assert sorted(result["matchedSkills"]) == ["Docker", "Flask", "MongoDB", "Python"]


def test_score_always_within_bounds():
    for _ in range(20):
        result = score("Python", job={"requiredSkills": ["Kubernetes", "Go"]}, embedder=PerfectSimilarity())
        assert 0 <= result["matchScore"] <= 100


def test_gazetteer_boundary_does_not_false_match_substrings():
    # "ts" must not match inside "its"; "js" not inside "a/jsons"
    cv = "a/jsons file and its handler"
    job = {"requiredSkills": ["TypeScript", "JavaScript"]}
    result = score(cv, job=job, embedder=PerfectSimilarity())
    assert result["matchedSkills"] == []
    assert sorted(result["missingSkills"]) == ["JavaScript", "TypeScript"]


def test_recommendations_are_templated_and_bounded():
    missing = ["Kubernetes", "Docker"]
    recommendations = ms.build_recommendations(missing, matched=["Python"])
    assert 1 <= len(recommendations) <= 3
    assert "Kubernetes" in recommendations[0]

    aligned = ms.build_recommendations([], matched=["Python"])
    assert len(aligned) == 1

    generic = ms.build_recommendations([], matched=[])
    assert len(generic) == 1


def test_score_cv_result_contract_keys():
    result = score("Python", embedder=PerfectSimilarity())
    assert set(result.keys()) == {
        "matchScore",
        "matchedSkills",
        "missingSkills",
        "recommendations",
        "modelVersion",
    }