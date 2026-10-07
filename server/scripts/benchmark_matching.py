"""M6 benchmark for the matching pipeline vs the <5s per-application NFR.

Run inside the server container (models are installed at image build):

    docker-compose exec -T server python -m scripts.benchmark_matching [--tfidf-only]

Measures a realistic CV-vs-job scoring call:
  - cold: first call in the process (lazy spaCy/sentence-transformers load)
  - warm: steady-state per-application latency

Exits non-zero if the warm call exceeds the 5s NFR. ``--tfidf-only`` forces the
keyword fallback (useful on machines without a model cache).
"""
import argparse
import sys
import time
from typing import Any

from app.services.matching_service import score_cv

JOB: dict[str, Any] = {
    "title": "Backend Engineer",
    "description": (
        "Build REST APIs with Python and Flask backed by MongoDB. Own Dockerised "
        "deployments, write tests, and improve pipeline performance."
    ),
    "requiredSkills": ["Python", "Flask", "MongoDB", "Docker", "Testing", "SQL"],
}

CV_TEXT = """
Backend Engineer with five years of Python experience. Designed and shipped REST APIs
in Flask against MongoDB at scale, containerised services with Docker, and maintained a
CI/CD rig with automated tests using pytest. Comfortable with SQL and relational
modelling. Led a migration that cut p95 latency by 40%.
"""

NFR_SECONDS = 5.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tfidf-only", action="store_true", help="force the TF-IDF scorer")
    args = parser.parse_args()
    if args.tfidf_only:
        import os

        os.environ["MATCH_EMBEDDINGS_DISABLED"] = "true"

    start = time.perf_counter()
    result = score_cv(CV_TEXT, JOB)
    cold = time.perf_counter() - start

    warm_runs = 5
    start = time.perf_counter()
    for _ in range(warm_runs):
        score_cv(CV_TEXT, JOB)
    warm = (time.perf_counter() - start) / warm_runs

    print(f"matchScore={result['matchScore']} model={result['modelVersion']}")
    print(f"cold:  {cold * 1000:.0f}ms  (one-off model load)")
    print(f"warm:  {warm * 1000:.0f}ms  (steady state)")
    print(f"NFR:   {NFR_SECONDS * 1000:.0f}ms per application  ->  {'PASS' if warm <= NFR_SECONDS else 'FAIL'}")

    return 0 if warm <= NFR_SECONDS else 1


if __name__ == "__main__":
    sys.exit(main())