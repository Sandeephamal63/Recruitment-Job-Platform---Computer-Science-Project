"""M7 evaluation harness: run the shipped matching pipeline against the curated
dataset and produce report-ready evidence (skills precision/recall, score
plausibility by label, per-case attention flags).

Run inside the server container (models are installed at image build):

    docker-compose exec -T server python -m scripts.evaluate_matching

Dataset location: ``$EVAL_DATA_DIR`` (set by docker-compose) or
``<repo>/data/evaluation`` on bare metal. Writes ``results.md`` and
``results.json`` next to the dataset.

Exit code is non-zero when a sanity guard fails:
  - every case produces a well-formed score
  - aggregate skill recall >= 0.9
  - mean score ordering holds: strong > ok > weak
"""
import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.matching_service import score_cv

# Score bands used ONLY as a diagnostic (not a guard): a strong case scoring
# below its band is flagged for attention in the report rather than failing CI.
BANDS: dict[str, tuple[float, float]] = {
    "strong": (60.0, 101.0),
    "ok": (35.0, 85.0),
    "weak": (-1.0, 55.0),
}


def _data_dir() -> Path:
    override = Path(__import__("os").environ.get("EVAL_DATA_DIR", ""))
    if override and override.is_dir():
        return override
    return Path(__file__).resolve().parents[2] / "data" / "evaluation"


def _load_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _run_case(case: dict[str, Any], job: dict[str, Any], cv_text: str) -> dict[str, Any]:
    result = score_cv(cv_text, job)
    expected_matched = set(case["expectedMatched"])
    expected_missing = set(case["expectedMissing"])
    got_matched = set(result["matchedSkills"])
    got_missing = set(result["missingSkills"])

    found = expected_matched & got_matched
    extra = got_matched - expected_matched
    missed = expected_matched - got_matched

    precision = len(found) / len(got_matched) if got_matched else (1.0 if not found else 0.0)
    recall = len(found) / len(expected_matched) if expected_matched else 1.0

    label = case["plausibility"]
    low, high = BANDS[label]
    aligned = low <= result["matchScore"] < high
    attention = (
        len(missed) > 0
        or len(extra) > 0
        or set(got_missing) != expected_missing
        or not aligned
    )

    return {
        "id": case["id"],
        "jobId": case["jobId"],
        "plausibility": label,
        "score": result["matchScore"],
        "modelVersion": result["modelVersion"],
        "matched": result["matchedSkills"],
        "missing": result["missingSkills"],
        "expectedMatched": case["expectedMatched"],
        "expectedMissing": case["expectedMissing"],
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "misDetected": sorted(missed | extra),
        "bandAligned": aligned,
        "attention": bool(attention),
    }


def _aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_label: dict[str, list[int]] = {label: [] for label in BANDS}
    for run in runs:
        by_label[run["plausibility"]].append(run["score"])

    def summarize(scores: list[int]) -> dict[str, float] | None:
        if not scores:
            return None
        return {"count": len(scores), "mean": statistics.mean(scores), "median": statistics.median(scores)}

    total_expected = sum(len(run["expectedMatched"]) for run in runs)
    total_found = sum(
        len(set(run["matched"]) & set(run["expectedMatched"])) for run in runs
    )
    return {
        "cases": len(runs),
        "attentionCases": sum(1 for run in runs if run["attention"]),
        "perLabel": {label: summarize(by_label[label]) for label in BANDS},
        "skillRecall": round(total_found / total_expected, 3) if total_expected else 1.0,
    }


def _render_markdown(runs: list[dict[str, Any]], aggregate: dict[str, Any]) -> str:
    lines = [
        "# Matching evaluation results",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}Z by "
        f"`scripts/evaluate_matching.py`._",
        "",
        "Per-case verdict = `score / plausibility band` + skill agreement with the "
        "hand-labelled expectations. `attention` marks a case worth reading in the report.",
        "",
        "| case | job | label | score | skills (found/expected) | recall | precision | attention |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for run in runs:
        skills = f"{len(run['matched'])}/{len(run['expectedMatched'])}"
        lines.append(
            f"| {run['id']} | {run['jobId']} | {run['plausibility']} | {run['score']} "
            f"| {skills} | {run['recall']:.2f} | {run['precision']:.2f} | "
            f"{'yes' if run['attention'] else ''} |"
        )
    lines += ["", "## Aggregates", ""]
    lines.append(f"- Cases: **{aggregate['cases']}** ({aggregate['attentionCases']} flagged for attention)")
    lines.append(f"- Aggregate skill recall (matched∩expected / expected): **{aggregate['skillRecall']:.2%}**")
    for label, stats in aggregate["perLabel"].items():
        if stats:
            lines.append(
                f"- `{label}` (n={stats['count']}): mean **{stats['mean']:.0f}**, median **{stats['median']:.0f}**"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true", help="print; do not write results files")
    args = parser.parse_args()

    data_dir = _data_dir().resolve()
    jobs = {job["id"]: job for job in _load_json(data_dir / "jobs.json")}
    cases = _load_json(data_dir / "cases.json")
    runs: list[dict[str, Any]] = []

    for case in cases:
        job = jobs[case["jobId"]]
        cv_text = (data_dir / "cvs" / case["cvFile"]).read_text(encoding="utf-8")
        runs.append(_run_case(case, job, cv_text))

    aggregate = _aggregate(runs)

    by_label = aggregate["perLabel"]
    means = {label: stats["mean"] for label, stats in by_label.items() if stats}
    strong, ok, weak = means.get("strong"), means.get("ok"), means.get("weak")
    ordering_checks: list[bool] = []
    if strong is not None and ok is not None:
        ordering_checks.append(strong > ok)
    if ok is not None and weak is not None:
        ordering_checks.append(ok > weak)
    if strong is not None and weak is not None:
        ordering_checks.append(strong > weak)

    guards: list[tuple[str, bool]] = [
        ("all cases produced a well-formed score", all("score" in run for run in runs)),
        (
            "aggregate skill recall >= 0.9",
            aggregate["skillRecall"] >= 0.9,
        ),
        ("mean score ordering strong > ok > weak", all(ordering_checks)),
    ]

    if not args.no_write:
        (data_dir / "results.md").write_text(_render_markdown(runs, aggregate), encoding="utf-8")
        payload = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "detail": runs,
            "aggregate": aggregate,
            "guards": {name: ok for name, ok in guards},
        }
        (data_dir / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for label, stats in by_label.items():
        if stats:
            print(f"  {label:6s} n={stats['count']:2d}  mean={stats['mean']:5.1f}  median={stats['median']:3.0f}")
    print(f"skill recall: {aggregate['skillRecall']:.1%}  ({aggregate['attentionCases']}/{aggregate['cases']} attention)")

    failed = any(not ok for _, ok in guards)
    for name, ok in guards:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    for run in runs:
        if run["attention"]:
            print(f"  attention: {run['id']} score={run['score']} misDetected={run['misDetected']} bandAligned={run['bandAligned']}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())