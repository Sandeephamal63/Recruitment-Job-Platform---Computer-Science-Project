"""P1.0 demo seed: a realistic slice of the platform in an empty database.

Why this exists
---------------
The critique of the pre-product build was that a fresh install looked broken:
no employers on public jobs, empty dashboards, no applicants, and an evaluation
report whose scores could never disagree with itself. A demo (and a reviewer
running ``docker-compose up``) needs data that behaves like real data:

  - every job shows a real company with an industry, size and description
  - every application has a downloadable PDF CV and a match score produced by
    the *shipped* pipeline (``matching_service.score_cv``), not a hand-written
    number
  - statuses are spread across the funnel so the funnel chart, the filters and
    the bulk actions all have something to show
  - rejection reasons and employer notes exist because the UI was built for them

Run inside the server container (models are installed at image build):

    docker-compose exec -T server python -m scripts.seed_demo --reset

``--reset`` drops the domain collections first; without it the script refuses to
run, so a seeded demo can never be silently duplicated.

Dataset location: ``$EVAL_DATA_DIR`` (set by docker-compose) or
``<repo>/data/evaluation``. The evaluation CVs are reused as the demo CVs so the
demo and the M7 report agree on the same skills vocabulary.
"""
import argparse
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

from bson import ObjectId

from app import create_app
from app.db import get_db
from app.repositories.application_repository import ApplicationRepository
from app.repositories.cv_repository import CVRepository
from app.repositories.job_repository import JobRepository
from app.repositories.match_result_repository import MatchResultRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.job_service import JobService
from app.services.matching_service import score_cv
from app.utils.time import end_of_day, utcnow
from scripts.simple_pdf import build_text_pdf

DEMO_PASSWORD = "DemoPass123!"

EMPLOYERS: list[dict[str, Any]] = [
    {
        "email": "hiring@northwind.example",
        "name": "Rowan Ellis",
        "companyName": "Northwind Analytics",
        "companyDescription": (
            "We sell decision-support tooling to logistics operators. Forty-two people, "
            "one product, and a Python shop that ships every week. Our platform team owns "
            "the ingestion pipeline and the APIs the customer dashboard runs on."
        ),
        "companyIndustry": "Data & Analytics",
        "companySize": "51-200",
    },
    {
        "email": "careers@tidewater.example",
        "name": "Imani Adeyemi",
        "companyName": "Tidewater Labs",
        "companyDescription": (
            "A mid-stage product company building scheduling software for community "
            "clinics. Small teams, high ownership, and a bias for boring technology "
            "that stays maintainable."
        ),
        "companyIndustry": "Software",
        "companySize": "11-50",
    },
]

# Each candidate is pinned to one evaluation CV so the seeded match scores use the
# same inputs the M7 report scores.
CANDIDATES: list[dict[str, Any]] = [
    {
        "email": "priya.raman@example.dev",
        "name": "Priya Raman",
        "headline": "Senior Frontend Engineer",
        "cvFile": "frontend-strong.txt",
        "skills": ["React", "TypeScript", "GraphQL", "CSS", "Testing Library"],
    },
    {
        "email": "marcus.feld@example.dev",
        "name": "Marcus Feld",
        "headline": "Backend Engineer",
        "cvFile": "backend-strong.txt",
        "skills": ["Python", "Flask", "MongoDB", "Docker", "SQL", "REST"],
    },
    {
        "email": "sofia.marino@example.dev",
        "name": "Sofia Marino",
        "headline": "Full-stack Engineer",
        "cvFile": "fullstack-strong.txt",
        "skills": ["React", "TypeScript", "Node.js", "PostgreSQL", "Docker"],
    },
    {
        "email": "amara.osei@example.dev",
        "name": "Dr Amara Osei",
        "headline": "Data Scientist",
        "cvFile": "datasci-strong.txt",
        "skills": ["Python", "pandas", "scikit-learn", "SQL", "Statistics"],
    },
    {
        "email": "tomas.novak@example.dev",
        "name": "Tomas Novak",
        "headline": "Platform Engineer",
        "cvFile": "devops-strong.txt",
        "skills": ["Docker", "Kubernetes", "AWS", "Terraform", "CI/CD"],
    },
    {
        "email": "lena.fischer@example.dev",
        "name": "Lena Fischer",
        "headline": "Frontend Developer",
        "cvFile": "frontend-partial.txt",
        "skills": ["React", "CSS", "JavaScript"],
    },
    {
        "email": "yuki.tanaka@example.dev",
        "name": "Yuki Tanaka",
        "headline": "Data Analyst",
        "cvFile": "dataanalyst-strong.txt",
        "skills": ["SQL", "Python", "pandas", "Power BI"],
    },
    {
        "email": "daniel.okafor@example.dev",
        "name": "Daniel Okafor",
        "headline": "Junior Web Developer",
        "cvFile": "fullstack-weak.txt",
        "skills": ["HTML", "CSS", "JavaScript"],
    },
]

# The nine roles come straight from the evaluation dataset so seeded scores are
# reproducible against ``data/evaluation/results.json``.
#
# ``deadlineInDays`` is an offset from the seed run, not a literal date, so the
# demo never rots: a hardcoded closing date would quietly turn every posting into
# an expired one the first time it was re-seeded. ``-1`` on ``data-scientist``
# is deliberate — it is the one role the demo shows expiring, so the derived
# close is visible in the employer list without opening a second terminal.
# ``security`` keeps a *future* deadline while being closed, so the demo shows
# both kinds of closure: closed by the employer, and closed by the date.
JOB_DETAILS: dict[str, dict[str, Any]] = {
    "backend-python": {
        "employer": 0, "location": "Manchester, UK", "employmentType": "full-time",
        "salaryMin": 62000, "salaryMax": 78000, "experienceLevel": "mid", "remote": True,
        "deadlineInDays": 30,
    },
    "frontend-react": {
        "employer": 1, "location": "Bristol, UK", "employmentType": "full-time",
        "salaryMin": 55000, "salaryMax": 70000, "experienceLevel": "mid", "remote": True,
        "deadlineInDays": 21,
    },
    "fullstack": {
        "employer": 1, "location": "Remote (UK)", "employmentType": "full-time",
        "salaryMin": 58000, "salaryMax": 72000, "experienceLevel": "mid", "remote": True,
        "deadlineInDays": 45,
    },
    "data-scientist": {
        "employer": 0, "location": "Manchester, UK", "employmentType": "full-time",
        "salaryMin": 70000, "salaryMax": 88000, "experienceLevel": "senior", "remote": False,
        "deadlineInDays": -1,
    },
    "data-analyst": {
        "employer": 0, "location": "Leeds, UK", "employmentType": "full-time",
        "salaryMin": 45000, "salaryMax": 58000, "experienceLevel": "mid", "remote": True,
        "deadlineInDays": 14,
    },
    "devops": {
        "employer": 0, "location": "Remote (UK)", "employmentType": "full-time",
        "salaryMin": 65000, "salaryMax": 80000, "experienceLevel": "senior", "remote": True,
        "deadlineInDays": 28,
    },
    "qa": {
        "employer": 1, "location": "Bristol, UK", "employmentType": "contract",
        "salaryMin": 40000, "salaryMax": 52000, "experienceLevel": "mid", "remote": False,
        "deadlineInDays": 7,
    },
    "security": {
        "employer": 1, "location": "Bristol, UK", "employmentType": "full-time",
        "salaryMin": 68000, "salaryMax": 85000, "experienceLevel": "senior", "remote": False,
        "closed": True, "deadlineInDays": 60,
    },
    "product": {
        "employer": 1, "location": "Remote (UK)", "employmentType": "full-time",
        "salaryMin": 60000, "salaryMax": 78000, "experienceLevel": "lead", "remote": True,
        "deadlineInDays": 35,
    },
}

# (candidate email, job id, status, rejection reason or None)
APPLICATIONS: list[tuple[str, str, str, str | None]] = [
    ("marcus.feld@example.dev", "backend-python", "shortlisted", None),
    ("marcus.feld@example.dev", "devops", "rejected", "Kubernetes is the core requirement here"),
    ("marcus.feld@example.dev", "fullstack", "under_review", None),
    ("marcus.feld@example.dev", "data-scientist", "rejected", "Role needs modelling depth"),
    ("priya.raman@example.dev", "frontend-react", "shortlisted", None),
    ("priya.raman@example.dev", "fullstack", "under_review", None),
    ("priya.raman@example.dev", "product", "rejected", "Expects product discovery ownership"),
    ("priya.raman@example.dev", "qa", "rejected", "Not a testing-focused profile"),
    ("sofia.marino@example.dev", "fullstack", "shortlisted", None),
    ("sofia.marino@example.dev", "frontend-react", "under_review", None),
    ("sofia.marino@example.dev", "backend-python", "rejected", "Python depth below the bar"),
    ("sofia.marino@example.dev", "qa", "rejected", "Accepting an offer elsewhere"),
    ("sofia.marino@example.dev", "security", "rejected", "No security engineering background"),
    ("amara.osei@example.dev", "data-scientist", "shortlisted", None),
    ("amara.osei@example.dev", "data-analyst", "under_review", None),
    ("amara.osei@example.dev", "devops", "rejected", "Role is infrastructure, not modelling"),
    ("amara.osei@example.dev", "fullstack", "rejected", "Not a product engineering profile"),
    ("tomas.novak@example.dev", "devops", "shortlisted", None),
    ("tomas.novak@example.dev", "backend-python", "under_review", None),
    ("tomas.novak@example.dev", "data-analyst", "rejected", "Below the salary band"),
    ("lena.fischer@example.dev", "frontend-react", "submitted", None),
    ("lena.fischer@example.dev", "product", "under_review", None),
    ("lena.fischer@example.dev", "fullstack", "rejected", "Needs backend experience"),
    ("yuki.tanaka@example.dev", "data-analyst", "shortlisted", None),
    ("yuki.tanaka@example.dev", "data-scientist", "rejected", "Research experience too shallow"),
    ("yuki.tanaka@example.dev", "frontend-react", "rejected", "Different discipline"),
    ("daniel.okafor@example.dev", "frontend-react", "rejected", "Role filled internally"),
    ("daniel.okafor@example.dev", "fullstack", "withdrawn", None),
    ("daniel.okafor@example.dev", "product", "rejected", "Seniority mismatch"),
]

# (candidate email, job id, author, body) — the notes a recruiter actually wrote.
NOTES: list[tuple[str, str, str, str]] = [
    ("marcus.feld@example.dev", "backend-python", "Rowan Ellis", "Phone screen: solid on Flask internals, wants to stay on services."),
    ("priya.raman@example.dev", "frontend-react", "Imani Adeyemi", "Strong design systems work. Ask about the accessibility audit."),
    ("tomas.novak@example.dev", "devops", "Rowan Ellis", "Best infrastructure CV this cycle. Move fast."),
    ("yuki.tanaka@example.dev", "data-analyst", "Rowan Ellis", "Good SQL depth. Referred by the data team."),
]

SAVED_JOBS: list[tuple[str, list[str]]] = [
    ("lena.fischer@example.dev", ["frontend-react", "fullstack"]),
    ("yuki.tanaka@example.dev", ["data-scientist", "product"]),
    ("daniel.okafor@example.dev", ["frontend-react"]),
]

DOMAIN_COLLECTIONS = (
    "users", "jobs", "applications", "matchResults", "refreshTokens", "fs.files", "fs.chunks",
)


def data_dir() -> Path:
    override = Path(os.environ.get("EVAL_DATA_DIR", ""))
    if override and override.is_dir():
        return override
    return Path(__file__).resolve().parents[2] / "data" / "evaluation"


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a realistic demo dataset.")
    parser.add_argument("--reset", action="store_true", help="drop domain collections first")
    args = parser.parse_args()

    directory = data_dir().resolve()
    if not (directory / "jobs.json").is_file():
        print(f"error: no evaluation dataset at {directory}", file=sys.stderr)
        return 1

    app = create_app()
    with app.app_context():
        db = get_db()
        if args.reset:
            _reset(db)
        elif _has_data(db):
            print("database already has data — pass --reset to replace it", file=sys.stderr)
            return 1
        _seed(directory, db)
    return 0


def _has_data(db) -> bool:
    return bool(db.users.count_documents({}) or db.jobs.count_documents({}))


def _reset(db) -> None:
    for name in DOMAIN_COLLECTIONS:
        db.drop_collection(name)
    print("dropped:", ", ".join(DOMAIN_COLLECTIONS))


def _seed(directory: Path, db) -> None:
    users_repo = UserRepository(db)
    jobs_repo = JobRepository(db)
    applications_repo = ApplicationRepository(db)
    matches_repo = MatchResultRepository(db)
    cvs_repo = CVRepository(db)
    auth = AuthService(users_repo, RefreshTokenRepository(db))
    jobs_service = JobService(jobs_repo, users_repo, applications_repo, matches_repo)

    now = utcnow()
    employers = _seed_people(auth, users_repo, EMPLOYERS, "employer", now)
    candidates = _seed_people(auth, users_repo, CANDIDATES, "candidate", now)
    cv_texts = _seed_profile_cvs(cvs_repo, users_repo, candidates, directory, now)
    job_docs = _seed_jobs(jobs_service, jobs_repo, employers, directory, now)
    application_ids = _seed_applications(
        applications_repo, matches_repo, cvs_repo, candidates, job_docs, cv_texts, now
    )
    _seed_notes(applications_repo, application_ids, candidates, employers)
    _seed_saved_jobs(users_repo, candidates, job_docs)

    print(
        f"seeded {len(employers)} employers, {len(candidates)} candidates, "
        f"{len(job_docs)} jobs, {len(application_ids)} applications"
    )
    print()
    print(f"all demo logins use the password: {DEMO_PASSWORD}")
    for employer in EMPLOYERS:
        print(f"  employer   {employer['email']}")
    for candidate in CANDIDATES[:2]:
        print(f"  candidate  {candidate['email']}")
    print(f"  candidate  ({len(CANDIDATES)} total — see scripts/seed_demo.py CANDIDATES)")


def _seed_people(auth, users_repo, people: list[dict], role: str, now) -> dict[str, str]:
    ids: dict[str, str] = {}
    for index, person in enumerate(people):
        created = auth.register_user(
            {
                "role": role,
                "name": person["name"],
                "email": person["email"].lower(),
                "password": DEMO_PASSWORD,
                "companyName": person.get("companyName", ""),
                "headline": person.get("headline", ""),
                "skills": person.get("skills", []),
            }
        )
        user_id = str(created["_id"])
        updates: dict[str, Any] = {
            "createdAt": now - timedelta(days=90 - index * 7, hours=index * 3),
            "updatedAt": now,
        }
        for key in ("companyDescription", "companyIndustry", "companySize"):
            if person.get(key):
                updates[key] = person[key]
        users_repo.update(user_id, updates)
        ids[person["email"]] = user_id
    return ids


def _seed_profile_cvs(cvs_repo, users_repo, candidates, directory: Path, now) -> dict[str, str]:
    """One reusable CV per candidate, so the profile page and the
    'apply with saved CV' path have real bytes behind them."""
    texts: dict[str, str] = {}
    for email, candidate_id in candidates.items():
        person = _person(email)
        text = _read_cv(directory, person["cvFile"])
        texts[email] = text
        file_ref = cvs_repo.save(build_text_pdf(text, title=person["name"]), _cv_filename(person))
        users_repo.update(
            candidate_id,
            {"cvFileRef": ObjectId(file_ref), "cvParsedText": text, "updatedAt": now},
        )
    return texts


def _seed_jobs(jobs_service, jobs_repo, employers, directory: Path, now) -> dict[str, dict]:
    source_jobs = json.loads((directory / "jobs.json").read_text(encoding="utf-8"))
    documents: dict[str, dict] = {}
    for index, source in enumerate(source_jobs):
        details = JOB_DETAILS[source["id"]]
        created = jobs_service.create_job(
            employers[EMPLOYERS[details["employer"]]["email"]],
            {
                "title": source["title"],
                "description": source["description"],
                "requiredSkills": source["requiredSkills"],
                "location": details["location"],
                "employmentType": details["employmentType"],
                "salaryMin": details["salaryMin"],
                "salaryMax": details["salaryMax"],
                "currency": "GBP",
                "experienceLevel": details["experienceLevel"],
                "remote": details["remote"],
                # Already the stored end-of-day datetime: this script calls the
                # service directly, so unlike the API route it never passes
                # through the schema that does the string -> datetime step.
                "deadline": end_of_day(now.date() + timedelta(days=details["deadlineInDays"])),
            },
        )
        job_id = str(created["_id"])
        job = jobs_repo.update(
            job_id,
            {
                "createdAt": now - timedelta(days=40 - index * 3, hours=index * 5),
                "updatedAt": now,
                "status": "closed" if details.get("closed") else "open",
            },
        )
        documents[source["id"]] = job
    return documents


def _seed_applications(
    applications_repo, matches_repo, cvs_repo, candidates, job_docs, cv_texts, now
) -> dict[tuple[str, str], str]:
    """One application row plus its real match result per (candidate, job) pair."""
    ids: dict[tuple[str, str], str] = {}
    for index, (email, job_key, status, reason) in enumerate(APPLICATIONS):
        text = cv_texts[email]
        submitted_at = now - timedelta(days=28 - index % 25, hours=index * 2)
        file_ref = cvs_repo.save(build_text_pdf(text, title=_person(email)["name"]), _cv_filename(_person(email)))
        computed = score_cv(text, job_docs[job_key])
        document = {
            "jobId": job_docs[job_key]["_id"],
            "candidateId": ObjectId(candidates[email]),
            "cvFileRef": ObjectId(file_ref),
            "cvParsedText": text,
            "status": status,
            "notes": [],
            "withdrawn": status == "withdrawn",
            "submittedAt": submitted_at,
            "createdAt": submitted_at,
            "updatedAt": submitted_at,
        }
        if reason:
            document["rejectionReason"] = reason
        application_id = applications_repo.create(document)
        matches_repo.upsert_result(application_id, computed)
        ids[(email, job_key)] = application_id
    return ids


def _seed_notes(applications_repo, application_ids, candidates, employers) -> None:
    author_ids = {person["name"]: employers[person["email"]] for person in EMPLOYERS}
    for email, job_key, author, body in NOTES:
        application_id = application_ids.get((email, job_key))
        if not application_id:
            continue
        applications_repo.add_note(
            application_id,
            {
                "id": ObjectId(),
                "body": body,
                "authorUserId": ObjectId(author_ids[author]),
                "authorName": author,
                "createdAt": utcnow() - timedelta(hours=6),
            },
        )


def _seed_saved_jobs(users_repo, candidates, job_docs) -> None:
    for email, job_keys in SAVED_JOBS:
        for job_key in job_keys:
            users_repo.add_saved_job(candidates[email], job_docs[job_key]["_id"])


def _person(email: str) -> dict:
    return next(p for p in CANDIDATES if p["email"] == email)


def _cv_filename(person: dict) -> str:
    return person["name"].lower().replace(" ", "-") + "-cv.pdf"


def _read_cv(directory: Path, filename: str) -> str:
    path = directory / "cvs" / filename
    if not path.is_file():
        raise SystemExit(f"missing evaluation CV: {path}")
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
