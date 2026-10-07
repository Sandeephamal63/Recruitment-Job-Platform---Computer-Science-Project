import math
import os
from typing import Any

from .skills_gazetteer import diff_skills
SPACY_MODEL = "en_core_web_sm"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Blend is 50% skills overlap, 50% semantic similarity (0-1, mapped from cosine).
SKILLS_WEIGHT = 0.5
SEMANTIC_WEIGHT = 0.5

MODEL_VERSION_EMBEDDING = f"spacy-{SPACY_MODEL}-st-{EMBEDDING_MODEL}"
MODEL_VERSION_TFIDF = f"spacy-{SPACY_MODEL}-tfidf"

_nlp = None
_embedder = None


def _embeddings_disabled() -> bool:
    """Operational switch: set ``MATCH_EMBEDDINGS_DISABLED`` (truthy) to force
    the TF-IDF scorer in environments that cannot host the embedding model
    (e.g. CI without a model cache). Injected embedders always win over this."""
    return os.environ.get("MATCH_EMBEDDINGS_DISABLED", "").strip().lower() not in {
        "",
        "0",
        "false",
        "no",
    }


def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy

        _nlp = spacy.load(SPACY_MODEL)
    return _nlp


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def _preprocess(text: str) -> str:
    """Lemmatise and drop stopwords/punctuation/numbers for embedding input."""
    nlp = _get_nlp()
    tokens = [
        token.lemma_.lower()
        for token in nlp(text)
        if not token.is_stop
        and not token.is_punct
        and not token.is_space
        and not token.like_num
    ]
    return " ".join(tokens)


def _job_text(job: dict[str, Any]) -> str:
    parts = [str(job.get("title") or ""), str(job.get("description") or "")]
    parts.extend(str(skill) for skill in (job.get("requiredSkills") or []))
    return " ".join(part for part in parts if part)


def job_embedding(job: dict[str, Any], embedder=None, preprocess=None) -> list[float] | None:
    """The vector a job posting is searched by, over the same text it is scored on.

    Returns ``None`` when the model cannot be loaded, so a posting is never
    rejected because its vector could not be computed — the recommender falls
    back to TF-IDF for jobs without one.
    """
    try:
        return embed_text(_job_text(job), embedder, preprocess)
    except Exception:
        return None


def _map_cosine(cosine: float) -> float:
    """Map a cosine (-1..1) onto a 0..1 similarity to feed the blend."""
    return max(0.0, min(1.0, (cosine + 1.0) / 2.0))


def _encode(texts: list[str], embedder=None, preprocess=None) -> list[list[float]]:
    """Preprocess and embed a batch of texts with the shared model.

    The single place ``encode`` is called, so model resolution and preprocessing
    cannot drift between the per-application scorer and the recommender.

    Also the single place the operational switch is enforced for embedding:
    with ``MATCH_EMBEDDINGS_DISABLED`` set and no model injected, this raises
    rather than loading the model, so every caller falls through to its TF-IDF
    path. That keeps a host without a model cache (CI, an offline laptop) from
    silently paying a model download, and keeps job creation from writing
    vectors nothing will ever read. An injected embedder always wins, matching
    the rule in :func:`score_cv`.

    ``embedder``/``preprocess`` are injectable for unit tests (and programmes
    that need a deterministic scorer); defaults load the lazy singletons.
    """
    if embedder is None and preprocess is None and _embeddings_disabled():
        raise RuntimeError("embedding path disabled by MATCH_EMBEDDINGS_DISABLED")
    if embedder is None:
        embedder = _get_embedder()
    if preprocess is None:
        preprocess = _preprocess
    return embedder.encode(
        [preprocess(text) for text in texts], normalize_embeddings=True
    )


def embed_text(text: str, embedder=None, preprocess=None) -> list[float]:
    """Embed one already-known piece of text (a job posting or a profile).

    The vector a text receives does not depend on what else shares the batch —
    the model pools each sequence separately — so a vector stored on a document
    today is the vector :func:`score_cv` would compute for the same text.
    """
    return [float(value) for value in _encode([text], embedder, preprocess)[0]]


def _cosine_between(left: list[float], right: list[float]) -> float:
    """Cosine of two already-normalized vectors, mapped onto 0..1.

    Raises on a dimension mismatch or a non-finite result so a vector stored
    under a different model degrades to the TF-IDF scorer rather than scoring
    a silently truncated vector.
    """
    if len(left) != len(right):
        raise ValueError("embedding dimension mismatch")
    cosine = float(sum(a * b for a, b in zip(left, right)))
    if not math.isfinite(cosine):
        raise ValueError("non-finite embedding cosine")
    return _map_cosine(cosine)


def _score_with_embeddings(
    cv_text: str, job_text: str, embedder=None, preprocess=None
) -> float:
    """Semantic similarity scorer. Raises on any failure so the caller can fall
    back to keyword/TF-IDF scoring rather than degrade silently.
    """
    if not cv_text or not job_text:
        return 0.0

    vectors = _encode([cv_text, job_text], embedder, preprocess)
    return _cosine_between([float(v) for v in vectors[0]], [float(v) for v in vectors[1]])


def _score_with_tfidf(cv_text: str, job_text: str) -> float:
    """Keyword-overlap fallback scorer (scikit-learn TF-IDF cosine)."""
    if not cv_text or not job_text:
        return 0.0
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform([cv_text, job_text])
    cosine = float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
    return _map_cosine(cosine)


def build_recommendations(missing: list[str], matched: list[str]) -> list[str]:
    """2-3 template recommendations from the skill diff. Always returns >=1."""
    recommendations: list[str] = []
    for skill in missing[:2]:
        recommendations.append(
            f"Your CV does not mention {skill}. Add measurable experience with "
            f"{skill} to strengthen your application."
        )
    if not missing and matched:
        recommendations.append(
            "Your skills align well with this role — make the match explicit by "
            "leading your CV summary with the required skills."
        )
    if not recommendations:
        recommendations.append(
            "Tailor your CV for this role, calling out the required skills and "
            "related experience up front."
        )
    return recommendations[:3]


def build_match_result(
    required_skills: list[str],
    cv_text: str,
    semantic: float,
    model_version: str,
) -> dict[str, Any]:
    """Turn a (skills diff, semantic similarity) pair into a match result.

    The one place the blend, the skill diff, the score mapping and the
    recommendation templates are applied. :func:`score_cv` and
    :func:`score_candidate_against_jobs` both route through it, which is what
    makes a job score identically on the candidate dashboard and after the
    candidate applies to it — the two differ only in where ``semantic`` comes
    from (computed on the fly vs. read off stored vectors).
    """
    matched, missing = diff_skills(required_skills, cv_text)
    overlap = len(matched) / len(required_skills) if required_skills else None

    if overlap is None:
        score = semantic
    else:
        score = SKILLS_WEIGHT * overlap + SEMANTIC_WEIGHT * semantic

    return {
        "matchScore": round(max(0, min(100, score * 100))),
        "matchedSkills": matched,
        "missingSkills": missing,
        "recommendations": build_recommendations(missing, matched),
        "modelVersion": model_version,
    }


def score_cv(
    cv_text: str,
    job: dict[str, Any],
    embedder=None,
    preprocess=None,
) -> dict[str, Any]:
    """Score a parsed CV against a job document (M0 contract, now implemented).

    Pure and swappable: text in, score out. Persistence is a separate step in
    match_service. Blend is semantic similarity + skills-overlap ratio, both
    mapped to 0..1, so a strong overlap can rescue a weak semantic match and
    vice versa. Falls back to TF-IDF keyword overlap if the embedding path
    errors or produces a non-finite score.

    ``embedder``/``preprocess`` are injected by tests to avoid model loading;
    production uses the lazy model singletons (see ``_score_with_embeddings``).
    """
    cv_text = (cv_text or "").strip()
    required_skills = [str(skill) for skill in (job.get("requiredSkills") or [])]

    job_text = _job_text(job)
    if not cv_text:
        semantic = 0.0
        model_version = MODEL_VERSION_EMBEDDING
    elif (embedder is None and preprocess is None) and _embeddings_disabled():
        semantic = _score_with_tfidf(cv_text, job_text)
        model_version = MODEL_VERSION_TFIDF
    else:
        try:
            semantic = _score_with_embeddings(cv_text, job_text, embedder, preprocess)
            model_version = MODEL_VERSION_EMBEDDING
        except Exception:
            semantic = _score_with_tfidf(cv_text, job_text)
            model_version = MODEL_VERSION_TFIDF

    return build_match_result(required_skills, cv_text, semantic, model_version)


def score_candidate_against_jobs(
    cv_text: str,
    jobs: list[dict[str, Any]],
    profile_embedding: list[float] | None = None,
    limit: int = 10,
    embedder=None,
    preprocess=None,
) -> list[dict[str, Any]]:
    """Rank jobs for one candidate through the same blend :func:`score_cv` uses.

    The proactive counterpart to :func:`score_cv`: instead of one CV against one
    job, one profile against every open job. The semantic term for a job is a
    cosine against its stored ``embedding`` — the same dot product
    :func:`_score_with_embeddings` computes for the same text pair — so the
    two flows agree on a job's score by construction rather than by convention.

    A job with no stored vector, or one stored by a different model version, or
    every job when embeddings are disabled, falls back to the per-pair TF-IDF
    scorer. That is deliberately not batched: ``TfidfVectorizer`` derives its idf
    weights from the corpus it is fitted on, so a single fit over N documents
    would not reproduce the two-document fit :func:`score_cv` performs and the two
    flows would drift apart.

    The stored-model check matters on a corpus that has not been fully
    backfilled after a model upgrade: comparing a current-model candidate vector
    against a previous-model job vector is a dot product between two unrelated
    spaces, and its output is a confident number rather than a recognisable
    failure. Refusing those pairs and falling back is what makes a partially
    migrated corpus rank sanely while ``make db-embeddings`` catches up.

    Rows are descending by score (ties keep the order the repository returned,
    since the sort is stable) and truncated to ``limit``. Each row is a match
    result plus the ``jobId`` the ranking is keyed on.
    """
    cv_text = (cv_text or "").strip()
    if profile_embedding is None and cv_text and not _embeddings_disabled():
        try:
            profile_embedding = embed_text(cv_text, embedder, preprocess)
        except Exception:
            profile_embedding = None

    ranked: list[dict[str, Any]] = []
    for job in jobs:
        vector = job.get("embedding")
        if (
            profile_embedding is not None
            and vector
            and job.get("embeddingModel") == MODEL_VERSION_EMBEDDING
        ):
            try:
                semantic = _cosine_between(profile_embedding, [float(v) for v in vector])
                model_version = MODEL_VERSION_EMBEDDING
            except (ValueError, TypeError):
                semantic = _score_with_tfidf(cv_text, _job_text(job))
                model_version = MODEL_VERSION_TFIDF
        else:
            semantic = _score_with_tfidf(cv_text, _job_text(job))
            model_version = MODEL_VERSION_TFIDF

        required_skills = [str(skill) for skill in (job.get("requiredSkills") or [])]
        result = build_match_result(required_skills, cv_text, semantic, model_version)
        ranked.append({"jobId": str(job["_id"]), **result})

    ranked.sort(key=lambda row: row["matchScore"], reverse=True)
    return ranked[:limit]
