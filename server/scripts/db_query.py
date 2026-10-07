"""Database operations for local development: inspect, verify, reset.

Why this exists
---------------
The API is the only supported way to *change* data, but debugging regularly
needs to answer questions the API cannot: which indexes actually exist, whether
any document is orphaned, what a stored ``cvParsedText`` really contains,
whether the score in the database is the score the dashboard showed. Those are
questions about Mongo, so they live in one script that talks to Mongo directly
instead of being re-typed into ``mongosh`` sessions and forgotten.

Run inside the server container (compose supplies ``MONGO_URI`` /
``MONGO_DB_NAME``). The Makefile is the intended entry point:

    make db-info
    make db-indexes
    make db-user EMAIL=hiring@northwind.example
    make db-applicants JOB_ID=66f0...
    make db-embeddings YES=1
    make db-truncate YES=1

Everything else, including every flag:

    docker-compose exec -T server python -m scripts.db_query --help

The connection is built from ``config.Config`` rather than ``create_app()`` on
purpose: the factory calls ``ensure_indexes()``, which would create the very
indexes ``indexes`` exists to verify, making the check self-fulfilling.

Read vs write: only ``truncate``, ``reindex`` and ``embeddings`` write. All
three print what they will change and require confirmation; end-of-input
aborts, so a non-interactive shell can never get an implicit "yes". ``--yes``
skips the prompt (what ``make db-truncate YES=1`` and ``make db-reset`` pass).

Where a command answers something the product already answers (funnel, score
distribution, the applicant list) it calls the shipped repository method rather
than re-typing the aggregation, so the script cannot drift from the app.
``explain`` is the one exception: it needs the raw pipeline in order to report
the plan Mongo actually chose.

Exit codes: 0 fine, 1 a declared index is missing (``indexes``) or a write was
aborted, 2 the database could not be reached or an argument was wrong.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from bson import ObjectId
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from config import Config

GRIDFS_COLLECTIONS = ("fs.files", "fs.chunks")
SYSTEM_DATABASES = frozenset({"admin", "config", "local"})
PING_TIMEOUT_MS = 1500
DEFAULT_CV_PREVIEW = 500
DEFAULT_PAGE_SIZE = 50
EXPIRY_WINDOW = timedelta(hours=24)
PLAN_STAGES = frozenset(
    {"IXSCAN", "COLLSCAN", "FETCH", "SORT", "EQ_LOOKUP", "COUNT_SCAN", "PROJECTION_SIMPLE"}
)


def _table(title: str, headers: list[str], rows: list[list[Any]], notes: list[str] | None = None) -> dict:
    return {"kind": "table", "title": title, "headers": headers, "rows": rows, "notes": notes or []}


def _pairs(title: str, pairs: list[tuple[str, Any]], notes: list[str] | None = None) -> dict:
    return {"kind": "pairs", "title": title, "pairs": pairs, "notes": notes or []}


def _sections(sections: list[Any], notes: list[str] | None = None) -> dict:
    """Sections are either `(title, headers, rows)` triples or nested result
    documents, so a command can group a table next to a raw text block."""
    normalised: list[dict] = []
    for section in sections:
        if isinstance(section, dict) and "kind" in section:
            normalised.append(section)
        else:
            title, headers, rows = section
            normalised.append({"title": title, "headers": headers, "rows": rows})
    return {"kind": "sections", "sections": normalised, "notes": notes or []}


def _text_block(title: str, body: str, notes: list[str] | None = None) -> dict:
    return {"kind": "text", "title": title, "body": body, "notes": notes or []}


def _text(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        moment = value if value.tzinfo is None else value.astimezone(timezone.utc)
        return moment.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, float):
        return f"{value:.1f}"
    if isinstance(value, (list, tuple)):
        return ", ".join(_text(item) for item in value) or "-"
    if isinstance(value, dict):
        return ", ".join(f"{key}={_text(item)}" for key, item in value.items()) or "-"
    return str(value)


def _megabytes(size: int | float | None) -> str:
    if size is None:
        return "-"
    return f"{size / 1_048_576:.2f} MB"


def _kilobytes(size: int | float | None) -> str:
    if size is None:
        return "-"
    return f"{size / 1024:.1f} KB"


def _duration(delta: timedelta | int | float | None) -> str:
    if delta is None:
        return "-"
    seconds = int(delta.total_seconds() if isinstance(delta, timedelta) else delta)
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days:
        return f"{sign}{days}d {hours}h"
    if hours:
        return f"{sign}{hours}h {minutes}m"
    if minutes:
        return f"{sign}{minutes}m {seconds}s"
    return f"{sign}{seconds}s"


def _age(moment: datetime | None, now: datetime) -> str:
    if moment is None:
        return "-"
    return _duration(now - moment)


def _wrap(text: str, width: int = 100) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        while len(paragraph) > width:
            cut = paragraph.rfind(" ", 0, width)
            cut = cut if cut > 0 else width
            lines.append(paragraph[:cut])
            paragraph = paragraph[cut:].lstrip()
        lines.append(paragraph)
    return lines


def _render(result: dict) -> None:
    if result["kind"] == "table":
        _render_table(result)
    elif result["kind"] == "pairs":
        _render_pairs(result)
    elif result["kind"] == "text":
        print(f"\n{result['title']}")
        for line in result["body"].splitlines():
            print(f"  {line}")
    else:
        _render_sections(result)
    for note in result.get("notes", []):
        print(f"  note  {note}")


def _render_table(result: dict) -> None:
    print(f"\n{result['title']}")
    _print_grid(result["headers"], result["rows"])


def _render_pairs(result: dict) -> None:
    print(f"\n{result['title']}")
    width = max((len(label) for label, _ in result["pairs"]), default=0)
    for label, value in result["pairs"]:
        print(f"  {label.ljust(width)}  {_text(value)}")


def _has_content(result: dict) -> bool:
    kind = result.get("kind")
    if kind is None:
        return bool(result.get("rows"))
    if kind == "text":
        return bool(result["body"].strip())
    if kind == "pairs":
        return bool(result["pairs"])
    if kind == "sections":
        return any(_has_content(section) for section in result["sections"])
    return bool(result["rows"])


def _render_sections(result: dict) -> None:
    for section in result["sections"]:
        if not _has_content(section):
            continue
        if section.get("kind"):
            _render(section)
            continue
        print(f"\n{section['title']}")
        _print_grid(section["headers"], section["rows"])


def _print_grid(headers: list[str], rows: list[list[Any]]) -> None:
    cells = [[_text(value) for value in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in cells:
        for index, cell in enumerate(row):
            if index < len(widths):
                widths[index] = max(widths[index], len(cell))
    print("  " + "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    for row in cells:
        print("  " + "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))


def _database() -> Database:
    """Connect straight from config, bypassing ``create_app()`` (see module docstring)."""
    client = MongoClient(
        Config.MONGO_URI, serverSelectionTimeoutMS=PING_TIMEOUT_MS, tz_aware=False
    )
    try:
        client.admin.command("ping")
    except PyMongoError as error:
        print(f"error: cannot reach {Config.MONGO_URI} ({error})", file=sys.stderr)
        raise SystemExit(2)
    return client[Config.MONGO_DB_NAME]


def _utcnow() -> datetime:
    from app.utils.time import utcnow

    return utcnow()


def _object_id(value: str, label: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        print(f"error: {label} {value!r} is not a valid ObjectId", file=sys.stderr)
        raise SystemExit(2)
    return ObjectId(value)


def _require_job(db: Database, job_id: str) -> dict:
    from app.repositories.job_repository import JobRepository

    _object_id(job_id, "jobId")
    job = JobRepository(db).find_by_id(job_id)
    if job is None:
        print(f"error: no job with _id {job_id}", file=sys.stderr)
        raise SystemExit(2)
    return job


def _apply_declared_indexes() -> None:
    """Re-apply ``INDEX_SPECS`` without booting the application."""
    from flask import Flask

    from app.db import ensure_indexes

    app = Flask(__name__)
    app.config.from_object(Config)
    with app.app_context():
        ensure_indexes()


def _confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    try:
        answer = input(f"{prompt} type 'yes' to continue: ")
    except EOFError:
        print("aborted: no input available (pass --yes to confirm non-interactively)")
        return False
    if answer.strip().lower() in {"yes", "y"}:
        return True
    print("aborted")
    return False


def _wrap_text(body: str) -> str:
    return "\n".join(_wrap(body))


def _job_map(db: Database, job_ids: list[str]) -> dict[str, dict]:
    from app.repositories.job_repository import JobRepository

    found = JobRepository(db).find_by_ids(job_ids)
    return {str(job["_id"]): job for job in found}


def _user_map(db: Database, user_ids: list[str]) -> dict[str, dict]:
    from app.repositories.user_repository import UserRepository

    found = UserRepository(db).find_by_ids(user_ids)
    return {str(user["_id"]): user for user in found}


def _endpoints(client: MongoClient) -> str:
    """`MongoClient.address` is one (host, port) or a set of them once connected."""
    address = client.address
    if address and isinstance(address[0], (list, tuple)):
        return ", ".join(f"{host}:{port}" for host, port in address)
    return str(address)


def _index_keys(index: dict) -> list[tuple[str, Any]]:
    """`index_information()` reports `key` as a dict in older pymongo, a list of
    (field, direction) pairs in 4.9+. Normalise so both render the same."""
    keys = index["key"]
    if isinstance(keys, dict):
        return list(keys.items())
    return [tuple(pair) for pair in keys]


def _key_text(keys: list[tuple[str, Any]]) -> str:
    return ", ".join(f"{field}:{direction}" for field, direction in keys)


def _cmd_info(db: Database, args: argparse.Namespace) -> dict:
    client = db.client
    server = client.server_info()
    status = client.admin.command("replSetGetStatus")
    live = client.admin.command("serverStatus")
    my_state = status.get("myState")
    rows = [
        [
            member.get("name"),
            member.get("stateStr"),
            member.get("health"),
            _duration(member.get("uptime", 0) * 1000) if member.get("uptime") else None,
        ]
        for member in status.get("members", [])
    ]
    database_rows: list[list[Any]] = []
    for name in sorted(client.list_database_names()):
        if name in SYSTEM_DATABASES:
            continue
        stats = client[name].command("dbStats")
        database_rows.append(
            [
                name,
                "<-- selected" if name == db.name else None,
                stats.get("collections"),
                _megabytes(stats.get("dataSize")),
                _megabytes(stats.get("storageSize")),
                _megabytes(stats.get("totalSize")),
            ]
        )
    return _sections(
        [
            (
                "server",
                ["field", "value"],
                [
                    ["deployment", _endpoints(client)],
                    ["selected database", db.name],
                    ["version", server.get("version")],
                    ["process", live.get("process")],
                    ["uptime", _duration((live.get("uptime") or 0) * 1000)],
                    [
                        "connections",
                        "current={current} available={available} created={totalCreated}".format(
                            **live.get("connections", {})
                        ),
                    ],
                    ["replica set", f"{status.get('set')} (myState={my_state})"],
                ],
            ),
            ("replica set members", ["host", "state", "health", "uptime"], rows),
            (
                "databases",
                ["name", "", "collections", "data", "storage", "total"],
                database_rows,
            ),
        ],
        notes=[
            "storageSize is WiredTiger's on-disk size and lags the data size until a flush.",
            "a database other than the selected one (e.g. recruit_test) means a previous test run leaked.",
        ],
    )


def _cmd_collections(db: Database, args: argparse.Namespace) -> dict:
    names = sorted(db.list_collection_names())
    if not names:
        return _table("collections", ["collection", "documents", "data", "indexes", "index keys"], [])
    rows: list[list[Any]] = []
    for name in names:
        stats = db.command("collStats", name)
        index_info = db[name].index_information()
        rows.append(
            [
                name,
                stats.get("count"),
                _megabytes(stats.get("size")),
                _megabytes(stats.get("totalIndexSize")),
                len(index_info),
            ]
        )
    return _table(
        "collections",
        ["collection", "documents", "data", "index size", "indexes"],
        rows,
        notes=["a missing collection is simply absent from the database, not an error"],
    )


def _cmd_indexes(db: Database, args: argparse.Namespace) -> dict:
    from app.db import INDEX_SPECS

    names = [args.collection] if args.collection else sorted(db.list_collection_names())
    sections: list[tuple[str, list[str], list[list[Any]]]] = []
    for name in names:
        if name not in db.list_collection_names():
            print(f"error: no collection {name}", file=sys.stderr)
            raise SystemExit(2)
        rows: list[list[Any]] = []
        for index_name, info in db[name].index_information().items():
            options = {key: value for key, value in info.items() if key != "key"}
            rows.append([index_name, _key_text(_index_keys(info)), _text(options)])
        sections.append((name, ["index", "keys", "options"], rows))

    missing: list[list[Any]] = []
    for collection, keys, options in INDEX_SPECS:
        if args.collection and collection != args.collection:
            continue
        actual = {
            tuple(sorted(_index_keys(info)))
            for info in db[collection].index_information().values()
        }
        if {tuple(sorted(keys))} - actual:
            missing.append([collection, _key_text(keys), _text(options)])
    sections.insert(0, ("missing from INDEX_SPECS", ["collection", "keys", "options"], missing))
    unique_count = sum(1 for _collection, _keys, options in INDEX_SPECS if options.get("unique"))
    return _sections(
        sections,
        notes=[
            "INDEX_SPECS (server/app/db.py) is the declaration ensure_indexes applies; anything under"
            " 'missing' is absent from the running database.",
            f"the {unique_count} unique indexes are correctness guards, not performance aids: without"
            " them duplicate users, applications, match results or cached rankings become possible.",
        ],
    )


def _cmd_reindex(db: Database, args: argparse.Namespace) -> dict:
    from app.db import INDEX_SPECS

    targets = sorted({collection for collection, _, _ in INDEX_SPECS})
    if args.collection:
        if args.collection not in targets:
            print(f"error: {args.collection} has no declared indexes", file=sys.stderr)
            raise SystemExit(2)
        targets = [args.collection]
    for collection in targets:
        if collection not in db.list_collection_names():
            continue
        _confirm(f"drop every index on {collection} and recreate from spec?", args.yes)
        db[collection].drop_indexes()
    _apply_declared_indexes()
    return _pairs(
        "reindexed",
        [("collections", targets), ("recreated from", "app.db.INDEX_SPECS")],
        notes=["drop_indexes keeps the mandatory _id index"],
    )


def _cmd_embeddings(db: Database, args: argparse.Namespace) -> dict:
    """Store a search embedding for every job whose vector is absent or outdated.

    Jobs get their vector when they are created and whenever their text is
    edited, so the postings selected here are only those written before
    embeddings existed (or on a host with MATCH_EMBEDDINGS_DISABLED set) plus
    any left behind by a model upgrade. Those are not *broken* — the scorer falls
    back to TF-IDF for a vector it cannot compare — but they are not searched
    semantically, so backfilling them is what makes the dashboard ranking
    consistent across the whole corpus.

    Candidates are the missing and the mismatched, reported separately: they
    mean different things operationally (a fresh install versus a model
    migration) and an operator reading the output should be able to tell them
    apart at a glance.
    """
    from app.services.matching_service import MODEL_VERSION_EMBEDDING, job_embedding

    query: dict = {} if args.all else {"status": "open"}
    scope = "job" if args.all else "open job"

    candidates = list(db.jobs.find(query))
    missing = [job for job in candidates if not job.get("embedding")]
    outdated = [
        job
        for job in candidates
        if job.get("embedding") and job.get("embeddingModel") != MODEL_VERSION_EMBEDDING
    ]
    pending = missing + outdated
    if not pending:
        return _pairs(
            "embeddings",
            [("scanned", len(candidates)), ("backfilled", 0)],
            notes=[f"every {scope} already has a stored embedding for model {MODEL_VERSION_EMBEDDING}"],
        )

    if not _confirm(
            f"compute and store an embedding for {len(pending)} of {len(candidates)} {scope}s?",
            args.yes,
        ):
            raise SystemExit(1)

    embedded: list[tuple[str, str, str]] = []
    failed: list[str] = []
    for job in pending:
        vector = job_embedding(job)
        if vector is None:
            failed.append(str(job["_id"]))
            continue
        db.jobs.update_one(
            {"_id": job["_id"]},
            {"$set": {"embedding": vector, "embeddingModel": MODEL_VERSION_EMBEDDING}},
        )
        kind = "missing" if not job.get("embedding") else "outdated"
        embedded.append((str(job["_id"]), str(job.get("title") or "(untitled)"), kind))

    notes = [f"model {MODEL_VERSION_EMBEDDING}"]
    if failed:
        notes.append(
            f"{len(failed)} could not be embedded (model unavailable?) — they still rank via the"
            f" TF-IDF fallback: {', '.join(failed)}"
        )
    return _sections(
        [
            (
                "embedded",
                ("job _id", "title", "was"),
                embedded,
            )
        ],
        notes=[
            f"backfilled {len(embedded)} of {len(pending)} embedding(s) across"
            f" {len(candidates)} {scope}s ({len(missing)} missing, {len(outdated)} outdated)",
            *notes,
        ],
    )


def _cmd_expire_jobs(db: Database, args: argparse.Namespace) -> dict:
    """Set status=closed on every open posting whose deadline has passed.

    This command is *convergence*, not enforcement. Expiry is derived at read
    time — browse, the recommender and the apply path all treat a posting whose
    deadline has passed as closed without ever writing to it — so a job is
    closed the moment its date passes, whether or not this ever runs, and
    because there is no scheduler nothing is needed for that to hold.

    What it fixes is the stored ``status`` field, which is the employer's own
    deliberate action and is left alone otherwise. Until this is run, an expired
    posting still *reads* ``status: "open"`` to a direct database inspection and
    to the employer's own job list, which is confusing to look at even when
    every user-facing path already treats it correctly.

    With ``--dry-run`` it reports what it would change without asking.
    """
    from app.utils.time import utcnow

    now = utcnow()
    expired = list(
        db.jobs.find(
            {
                "status": "open",
                "deadline": {"$ne": None, "$lt": now},
            }
        )
    )
    rows = [
        (
            str(job["_id"]),
            str(job.get("title") or "(untitled)"),
            job["deadline"].date().isoformat(),
            str(job.get("employerId")),
        )
        for job in expired
    ]
    if not rows:
        return _pairs(
            "expire-jobs",
            [("scanned", db.jobs.count_documents({})), ("expired", 0)],
            notes=["no open posting has a deadline in the past"],
        )

    if args.dry_run:
        return _sections(
            [("would close", ("job _id", "title", "deadline", "employerId"), rows)],
            notes=[
                f"{len(rows)} open posting(s) have a deadline before {now.isoformat()};"
                " re-run without --dry-run to set status=closed",
                "expiry is already enforced at read time — this only converges the stored field",
            ],
        )

    if not _confirm(f"close {len(rows)} open job(s) whose deadline has passed?", args.yes):
        raise SystemExit(1)

    result = db.jobs.update_many(
        {"status": "open", "deadline": {"$ne": None, "$lt": now}},
        {"$set": {"status": "closed", "updatedAt": now}},
    )
    return _sections(
        [("closed", ("job _id", "title", "deadline", "employerId"), rows)],
        notes=[
            f"set status=closed on {result.modified_count} of {len(rows)} expired posting(s)",
            "moving the deadline forward on a closed job does not reopen it — the"
            " employer sets status=open again",
        ],
    )


def _cmd_user(db: Database, args: argparse.Namespace) -> dict:
    from app.repositories.application_repository import ApplicationRepository
    from app.repositories.user_repository import UserRepository

    users = UserRepository(db)
    user = users.find_by_email(args.email)
    if user is None:
        print(f"error: no user with email {args.email!r}", file=sys.stderr)
        raise SystemExit(2)
    user_id = str(user["_id"])

    jobs = [job for job in db.jobs.find({"employerId": user["_id"]})]
    applications = list(db.applications.find({"candidateId": user["_id"]}))
    job_titles = _job_map(db, [str(job["_id"]) for job in jobs])
    applicant_jobs = _job_map(db, [str(item["jobId"]) for item in applications])
    match_by_application = {
        str(match["applicationId"]): match
        for match in db.matchResults.find(
            {"applicationId": {"$in": [item["_id"] for item in applications]}}
        )
    }

    identity = [
        ("_id", user_id),
        ("role", user.get("role")),
        ("name", user.get("name")),
        ("email", user.get("email")),
        ("companyName", user.get("companyName")),
        ("headline", user.get("headline")),
        ("skills", user.get("skills")),
        ("saved jobs", user.get("savedJobIds")),
        ("profile cv", user.get("cvFileRef")),
        ("createdAt", user.get("createdAt")),
    ]
    job_rows = [
        [
            job["_id"],
            job.get("title"),
            job.get("status"),
            db.applications.count_documents({"jobId": job["_id"]}),
            job.get("createdAt"),
        ]
        for job in sorted(jobs, key=lambda item: item.get("createdAt") or datetime.min, reverse=True)
    ]
    application_rows = [
        [
            item["_id"],
            applicant_jobs.get(str(item["jobId"]), {}).get("title", "(missing job)"),
            item.get("status"),
            match_by_application.get(str(item["_id"]), {}).get("matchScore"),
            match_by_application.get(str(item["_id"]), {}).get("modelVersion"),
            item.get("submittedAt"),
        ]
        for item in sorted(
            applications, key=lambda row: row.get("submittedAt") or datetime.min, reverse=True
        )
    ]
    counts = ApplicationRepository(db).funnel_by_job(
        [str(item["jobId"]) for item in applications]
    )
    return _sections(
        [
            ("user", ["field", "value"], [[label, value] for label, value in identity]),
            ("jobs owned", ["_id", "title", "status", "applicants", "createdAt"], job_rows),
            (
                "applications",
                ["_id", "job", "status", "score", "model", "submittedAt"],
                application_rows,
            ),
            (
                "funnel across those jobs",
                ["job", "status", "count"],
                [
                    [job_titles.get(job_id, {}).get("title", job_id), status, count]
                    for job_id, stages in counts.items()
                    for status, count in stages.items()
                ],
            ),
        ],
        notes=[
            "an employer owns jobs; a candidate owns applications",
            f"users total: {db.users.count_documents({})}",
        ],
    )


def _cmd_gridfs(db: Database, args: argparse.Namespace) -> dict:
    references: dict[str, list[str]] = {}
    for collection, label in (("applications", "application"), ("users", "profile")):
        for document in db[collection].find({}, {"cvFileRef": 1}):
            reference = document.get("cvFileRef")
            if reference is not None:
                references.setdefault(str(reference), []).append(f"{label} {document['_id']}")

    # Company logos share the default bucket, so they have to be collected here
    # too or every logo would be reported as orphaned bytes.
    for document in db["users"].find({}, {"logoFileRef": 1}):
        reference = document.get("logoFileRef")
        if reference is not None:
            references.setdefault(str(reference), []).append(f"employer {document['_id']}")

    rows: list[list[Any]] = []
    orphans: list[list[Any]] = []
    for file_document in db["fs.files"].find():
        holders = references.get(str(file_document["_id"]), [])
        row = [
            file_document["_id"],
            file_document.get("filename"),
            _kilobytes(file_document.get("length")),
            file_document.get("chunkSize"),
            file_document.get("uploadDate"),
            ", ".join(holders) or None,
        ]
        (orphans if not holders else rows).append(row)

    return _sections(
        [
            ("referenced files", ["_id", "filename", "size", "chunk size", "uploaded", "held by"], rows),
            ("orphaned files", ["_id", "filename", "size", "chunk size", "uploaded", "held by"], orphans),
        ],
        notes=[
            "original CV and logo bytes live in GridFS; the document keeps only the fs.files _id",
            "as cvFileRef (applications, users) or logoFileRef (users)",
            "an orphaned file is bytes no document points at any more — a leak, not a bug in the app",
            f"chunks stored: {db['fs.chunks'].count_documents({})}",
        ],
    )


def _cmd_funnel(db: Database, args: argparse.Namespace) -> dict:
    from app.repositories.application_repository import ApplicationRepository

    if args.job_id:
        job_ids = [str(_require_job(db, args.job_id)["_id"])]
    else:
        job_ids = [str(job["_id"]) for job in db.jobs.find({}, {"_id": 1})]
    if not job_ids:
        return _table("funnel", ["job", "status", "applicants"], [])
    titles = _job_map(db, job_ids)
    funnel = ApplicationRepository(db).funnel_by_job(job_ids)
    rows = [
        [
            job_id,
            titles.get(job_id, {}).get("title", "(missing job)"),
            status,
            count,
        ]
        for job_id in job_ids
        for status, count in sorted(funnel.get(job_id, {}).items())
    ]
    return _table(
        "funnel",
        ["jobId", "title", "status", "applicants"],
        rows,
        notes=["ApplicationRepository.funnel_by_job — the same aggregation the employer dashboard uses"],
    )


def _cmd_applicants(db: Database, args: argparse.Namespace) -> dict:
    from app.repositories.application_repository import ApplicationRepository

    _require_job(db, args.job_id)
    applications, total = ApplicationRepository(db).page_for_job(
        args.job_id,
        args.status,
        args.min_score,
        args.sort,
        1,
        args.limit or DEFAULT_PAGE_SIZE,
    )
    if not applications:
        return _table("applicants", ["application", "candidate", "status", "score"], [])
    candidates = _user_map(db, [str(item["candidateId"]) for item in applications])
    rows: list[list[Any]] = []
    for item in applications:
        candidate = candidates.get(str(item["candidateId"]), {})
        match = item.get("match") or {}
        rows.append(
            [
                item["_id"],
                candidate.get("name"),
                candidate.get("email"),
                item.get("status"),
                match.get("matchScore"),
                match.get("modelVersion"),
                match.get("matchedSkills"),
                match.get("missingSkills"),
                item.get("submittedAt"),
            ]
        )
    return _table(
        f"applicants for job {args.job_id}",
        [
            "application",
            "candidate",
            "email",
            "status",
            "score",
            "model",
            "matched",
            "missing",
            "submittedAt",
        ],
        rows,
        notes=[
            f"{total} applicant(s) match the filter; showing at most {args.limit or DEFAULT_PAGE_SIZE}",
            "matchScore lives in matchResults, so the repository joins it in; the score column is"
            " '-' until the pipeline finishes.",
            "ApplicationRepository.page_for_job — the dashboard's own query",
        ],
    )


def _cmd_pending(db: Database, args: argparse.Namespace) -> dict:
    pipeline = [
        {
            "$lookup": {
                "from": "matchResults",
                "localField": "_id",
                "foreignField": "applicationId",
                "as": "match",
            }
        },
        {"$addFields": {"match": {"$arrayElemAt": ["$match", 0]}}},
        {"$match": {"$or": [{"match.matchScore": None}, {"match": {"$size": 0}}]}},
        {"$sort": {"submittedAt": 1}},
    ]
    unscored = list(db.applications.aggregate(pipeline))
    now = _utcnow()
    job_ids = [str(item["jobId"]) for item in unscored]
    titles = _job_map(db, job_ids)
    rows = [
        [
            item["_id"],
            titles.get(str(item["jobId"]), {}).get("title", "(missing job)"),
            item.get("status"),
            item.get("submittedAt"),
            _age(item.get("submittedAt"), now),
            item.get("cvFileRef"),
        ]
        for item in unscored
    ]
    by_model: dict[str, int] = {}
    for item in unscored:
        model = (item.get("match") or {}).get("modelVersion") or "(no match row)"
        by_model[model] = by_model.get(model, 0) + 1
    total = db.applications.count_documents({})
    if not unscored:
        return _pairs(
            "unscored applications",
            [("none", 0), ("applications scored", total)],
            notes=["every submission has a score, so nothing is waiting on the matching pipeline"],
        )
    return _sections(
        [
            (
                "by modelVersion",
                ["modelVersion", "count"],
                [[model, count] for model, count in sorted(by_model.items())],
            ),
            (
                "unscored applications (oldest first)",
                ["application", "job", "status", "submittedAt", "age", "cvFileRef"],
                rows,
            ),
        ],
        notes=[
            "every submission writes a placeholder matchResult; 'pending' means the pipeline has not"
            " filled it in yet, or a job edit reset it",
            f"total applications: {total}",
        ],
    )


def _cmd_distribution(db: Database, args: argparse.Namespace) -> dict:
    from app.repositories.application_repository import ApplicationRepository

    if args.job_id:
        job_ids = [str(_require_job(db, args.job_id)["_id"])]
    else:
        job_ids = [str(job["_id"]) for job in db.jobs.find({}, {"_id": 1})]
    if not job_ids:
        return _table("score distribution", ["band", "applicants"], [])
    bands = ApplicationRepository(db).score_distribution(job_ids)
    total = sum(band["count"] for band in bands)
    rows = [
        [band["band"], band["count"], f"{band['count'] / total * 100:.0f}%" if total else "-"]
        for band in bands
    ]
    return _table(
        "score distribution",
        ["band", "applicants", "share"],
        rows,
        notes=[
            "bands come from application_repository.SCORE_BAND_BOUNDARIES, so this is exactly what the"
            " employer dashboard renders",
            f"across {len(job_ids)} job(s), {total} application(s)",
        ],
    )


def _cmd_cv(db: Database, args: argparse.Namespace) -> dict:
    application = db.applications.find_one({"_id": _object_id(args.application_id, "applicationId")})
    if application is None:
        print(f"error: no application with _id {args.application_id}", file=sys.stderr)
        raise SystemExit(2)
    job = db.jobs.find_one({"_id": application["jobId"]})
    candidate = db.users.find_one({"_id": application["candidateId"]})
    match = db.matchResults.find_one({"applicationId": application["_id"]})
    stored = db["fs.files"].find_one({"_id": application.get("cvFileRef")}) or {}

    text = application.get("cvParsedText") or ""
    limit = args.chars or DEFAULT_CV_PREVIEW
    sections: list[dict] = [
        _pairs(
            "application",
            [
                ["applicationId", application["_id"]],
                ["candidate", candidate.get("name") if candidate else None],
                ["candidate email", candidate.get("email") if candidate else None],
                ["job", job.get("title") if job else None],
                ["job requiredSkills", job.get("requiredSkills") if job else None],
                ["status", application.get("status")],
                ["submittedAt", application.get("submittedAt")],
                ["cvFileRef", application.get("cvFileRef")],
                ["gridfs filename", stored.get("filename")],
                ["gridfs length", _kilobytes(stored.get("length"))],
                ["cvParsedText length", f"{len(text)} chars, {len(text.split())} words"],
            ],
        ),
        _pairs(
            "match result",
            [
                ["matchScore", (match or {}).get("matchScore")],
                ["modelVersion", (match or {}).get("modelVersion")],
                ["matchedSkills", (match or {}).get("matchedSkills")],
                ["missingSkills", (match or {}).get("missingSkills")],
                ["recommendations", (match or {}).get("recommendations")],
            ],
        ),
        _text_block(
            f"cvParsedText (first {min(limit, len(text))} chars)",
            _wrap_text(text[:limit]) or "(empty)",
        ),
    ]
    return _sections(
        sections,
        notes=[
            "cvParsedText is a per-application snapshot taken at submission; it is not re-parsed per view",
            "use `make db-cv APPLICATION_ID=... CHARS=2000` to read more",
        ],
    )


def _cmd_tokens(db: Database, args: argparse.Namespace) -> dict:
    now = _utcnow()
    horizon = now + EXPIRY_WINDOW
    total = db.refreshTokens.count_documents({})
    active = db.refreshTokens.count_documents({"expiresAt": {"$gt": now}})
    expiring = db.refreshTokens.count_documents({"expiresAt": {"$gt": now, "$lte": horizon}})
    expired = total - active
    by_user = list(
        db.refreshTokens.aggregate(
            [
                {"$group": {"_id": "$userId", "count": {"$sum": 1}, "newest": {"$max": "$createdAt"}}},
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]
        )
    )
    users = _user_map(db, [str(row["_id"]) for row in by_user if row["_id"] is not None])
    rows = [
        [
            row["_id"],
            users.get(str(row["_id"]), {}).get("email", "(missing user)"),
            row.get("count"),
            row.get("newest"),
            _age(row.get("newest"), now),
        ]
        for row in by_user
    ]
    return _sections(
        [
            (
                "refresh tokens",
                ["measure", "count"],
                [
                    ["total", total],
                    ["active", active],
                    [f"expiring within {_duration(EXPIRY_WINDOW)}", expiring],
                    ["expired (awaiting TTL)", expired],
                ],
            ),
            ("most sessions", ["userId", "email", "tokens", "newest", "age"], rows),
        ],
        notes=[
            "the token secret and its bcrypt hash are deliberately not selected by this command",
            "a non-zero 'expired' count is normal: the TTL monitor only reaps expired rows on its own"
            " roughly 60-second sweep",
        ],
    )


def _find_plan_explain(db: Database, command_document: dict) -> dict:
    try:
        return db.command({"explain": command_document, "verbosity": "executionStats"})
    except PyMongoError:
        return db.command({"explain": command_document})


def _first_winning_plan(node: Any) -> Optional[dict]:
    if isinstance(node, dict):
        if "winningPlan" in node:
            return node["winningPlan"]
        for value in node.values():
            found = _first_winning_plan(value)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _first_winning_plan(item)
            if found is not None:
                return found
    return None


def _plan_features(node: Any, stages: set[str] | None = None, indexes: set[str] | None = None) -> tuple[set[str], set[str]]:
    """Collect the stage kinds and index names inside one plan. Only ever called
    with the winning plan, so a rejected candidate cannot pollute the answer."""
    stages = stages if stages is not None else set()
    indexes = indexes if indexes is not None else set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"stage", "planNode"}:
                if value in PLAN_STAGES:
                    stages.add(value)
            elif key == "indexName":
                indexes.add(str(value))
            else:
                _plan_features(value, stages, indexes)
    elif isinstance(node, list):
        for item in node:
            _plan_features(item, stages, indexes)
    return stages, indexes


def _execution_stats(explain: dict) -> dict:
    def find(node: Any) -> Optional[dict]:
        if isinstance(node, dict):
            if "executionStats" in node:
                return node["executionStats"]
            for value in node.values():
                found = find(value)
                if found is not None:
                    return found
        elif isinstance(node, list):
            for item in node:
                found = find(item)
                if found is not None:
                    return found
        return None

    stats = find(explain) or {}
    return {
        "nReturned": stats.get("nReturned"),
        "docsExamined": stats.get("totalDocsExamined", stats.get("docsExamined")),
        "keysExamined": stats.get("totalKeysExamined", stats.get("keysExamined")),
        "executionTimeMillis": stats.get("executionTimeMillis"),
    }


def _cmd_explain(db: Database, args: argparse.Namespace) -> dict:
    _require_job(db, args.job_id)
    job_oid = _object_id(args.job_id, "jobId")
    lookup_pipeline = [
        {"$match": {"jobId": job_oid}},
        {
            "$lookup": {
                "from": "matchResults",
                "localField": "_id",
                "foreignField": "applicationId",
                "as": "match",
            }
        },
        {"$addFields": {"score": {"$ifNull": [{"$arrayElemAt": ["$match.matchScore", 0]}, -1]}}},
        {"$sort": {"score": -1}},
    ]
    candidates = [
        (
            "find + sort submittedAt",
            {"find": "applications", "filter": {"jobId": job_oid}, "sort": {"submittedAt": -1}},
        ),
        (
            "aggregate: lookup matchResults, sort score",
            {
                "aggregate": "applications",
                "pipeline": lookup_pipeline,
                "cursor": {},
            },
        ),
    ]
    rows: list[list[Any]] = []
    for label, command_document in candidates:
        explain = _find_plan_explain(db, command_document)
        plan = _first_winning_plan(explain) or {}
        stages, indexes = _plan_features(plan)
        stats = _execution_stats(explain)
        rows.append(
            [
                label,
                "yes" if "IXSCAN" in stages else "no",
                ", ".join(sorted(stages)) or None,
                ", ".join(sorted(indexes)) or None,
                stats.get("nReturned"),
                stats.get("docsExamined"),
                stats.get("keysExamined"),
                stats.get("executionTimeMillis"),
            ]
        )
    return _table(
        f"query plan for job {args.job_id}",
        [
            "query",
            "index used",
            "plan stages",
            "indexes in plan",
            "returned",
            "docs examined",
            "keys examined",
            "ms",
        ],
        rows,
        notes=[
            "only the winning plan is shown, so a rejected candidate index is not counted",
            "the find query's SORT stage is a blocking in-memory sort; the score query sorts inside the"
            " pipeline after its $lookup, so the index can only serve the filter, never the ordering",
            "run this after a large seed to see the cost difference between the two shapes",
        ],
    )


def _cmd_truncate(db: Database, args: argparse.Namespace) -> dict:
    if db.name in SYSTEM_DATABASES:
        print(f"error: refusing to truncate the system database {db.name}", file=sys.stderr)
        raise SystemExit(2)
    names = sorted(db.list_collection_names())
    counts = [(name, db[name].count_documents({})) for name in names]
    if not names:
        return _pairs("truncate", [("database", db.name), ("status", "already empty")])
    targets = [name for name in names if name not in GRIDFS_COLLECTIONS] if args.keep_cvs else names
    plan = _table(
        "about to remove",
        ["collection", "documents"],
        [[name, count] for name, count in counts if name in targets],
        notes=["--keep-cvs was given: fs.files and fs.chunks are kept" if args.keep_cvs else "this drops GridFS CV bytes too"],
    )
    _render(plan)
    if not _confirm(f"truncate {len(targets)} collection(s) in {db.name}?", args.yes):
        raise SystemExit(1)

    if args.keep_cvs:
        for name in targets:
            db.drop_collection(name)
    else:
        db.client.drop_database(db.name)
    _apply_declared_indexes()

    orphans: list[list[Any]] = []
    if args.keep_cvs:
        held = {
            str(reference)
            for collection in ("applications", "users")
            for reference in db[collection].find({}, {"cvFileRef": 1})
            if reference.get("cvFileRef") is not None
        }
        orphans = [
            [document["_id"], document.get("filename"), _kilobytes(document.get("length"))]
            for document in db["fs.files"].find()
            if str(document["_id"]) not in held
        ]
    return _sections(
        [
            (
                "removed",
                ["collection", "documents"],
                [[name, count] for name, count in counts if name in targets],
            ),
            ("orphaned CV files left behind", ["_id", "filename", "size"], orphans),
        ],
        notes=[
            "indexes were re-applied from app.db.INDEX_SPECS, so the unique guards are back"
            if not args.keep_cvs
            else "fs.* was kept, so the CV files above are now unreferenced bytes",
        ],
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.db_query",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--json", action="store_true", help="print the raw result as JSON instead of a table"
    )
    # Repeated on every subcommand so `--json` is accepted on either side of the
    # command name. SUPPRESS keeps the subparser from overwriting a value the
    # main parser already set.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print the raw result as JSON instead of a table",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add(name: str, handler: Callable, help_text: str) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(
            name,
            parents=[common],
            help=help_text,
            description=handler.__doc__,
        )
        sub.set_defaults(handler=handler)
        return sub

    add("info", _cmd_info, "server, replica set, connections and every database with its size")
    add("collections", _cmd_collections, "per-collection document counts and sizes")
    indexes = add("indexes", _cmd_indexes, "all indexes, plus anything INDEX_SPECS declares but Mongo lacks")
    indexes.add_argument("collection", nargs="?", help="limit to one collection")
    reindex = add("reindex", _cmd_reindex, "drop and recreate the declared indexes (guarded)")
    reindex.add_argument("collection", nargs="?", help="limit to one collection")
    reindex.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    embeddings = add(
        "embeddings", _cmd_embeddings, "backfill job search embeddings (guarded)"
    )
    embeddings.add_argument(
        "--all", action="store_true", help="include closed jobs (default: open jobs only)"
    )
    embeddings.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    expire = add(
        "expire-jobs", _cmd_expire_jobs, "converge status=closed on postings past their deadline"
    )
    expire.add_argument("--dry-run", action="store_true", help="report without writing")
    expire.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    user = add("user", _cmd_user, "one user with their jobs, applications and funnel")
    user.add_argument("email", help="exact email address")
    add("gridfs", _cmd_gridfs, "stored CV files, and which document holds each one")
    funnel = add("funnel", _cmd_funnel, "application counts per job and per status")
    funnel.add_argument("job_id", nargs="?", help="limit to one job")
    applicants = add("applicants", _cmd_applicants, "a job's applicants with their match score")
    applicants.add_argument("job_id", help="job _id")
    applicants.add_argument("--status", help="filter by application status")
    applicants.add_argument("--min-score", type=int, help="minimum match score")
    applicants.add_argument(
        "--sort", default="score-desc", choices=["score-desc", "score-asc", "newest", "oldest"]
    )
    applicants.add_argument("--limit", type=int, help=f"rows to show (default {DEFAULT_PAGE_SIZE})")
    add("pending", _cmd_pending, "applications whose match result is still pending")
    distribution = add("distribution", _cmd_distribution, "histogram of match scores")
    distribution.add_argument("job_id", nargs="?", help="limit to one job")
    cv = add("cv", _cmd_cv, "a stored CV's extracted text next to its job and match result")
    cv.add_argument("application_id", help="application _id")
    cv.add_argument("--chars", type=int, help=f"preview length (default {DEFAULT_CV_PREVIEW})")
    add("tokens", _cmd_tokens, "refresh token counts per user (never prints secrets)")
    explain = add("explain", _cmd_explain, "query plan for a job's applicant list")
    explain.add_argument("job_id", help="job _id")
    truncate = add("truncate", _cmd_truncate, "drop collections and re-apply indexes (guarded)")
    truncate.add_argument("--keep-cvs", action="store_true", help="keep GridFS files")
    truncate.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    db = _database()
    print(f"mongodb  {Config.MONGO_URI}  ->  database {db.name!r}", file=sys.stderr)
    result = args.handler(db, args)
    if args.json:
        print(json.dumps(result, indent=2, default=_json_default))
    else:
        _render(result)
    if args.command == "indexes":
        return 1 if result["sections"][0]["rows"] else 0
    return 0


def _json_default(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


if __name__ == "__main__":
    sys.exit(main())
