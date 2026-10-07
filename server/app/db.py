from typing import Any, Optional

from flask import current_app
from pymongo import MongoClient
from pymongo.database import Database

_client: Optional[MongoClient] = None

# Every index the application relies on, declared once: `ensure_indexes` creates
# them, and dev tooling (`scripts/db_query.py indexes`) reports any that are
# missing, so the two can never disagree about what should exist.
INDEX_SPECS: tuple[tuple[str, list[tuple[str, Any]], dict[str, Any]], ...] = (
    ("users", [("email", 1)], {"unique": True}),
    ("refreshTokens", [("tokenId", 1)], {"unique": True}),
    ("refreshTokens", [("expiresAt", 1)], {"expireAfterSeconds": 0}),
    ("jobs", [("employerId", 1), ("status", 1)], {}),
    # Public browse is always "open, newest first"; the index carries the sort.
    ("jobs", [("status", 1), ("createdAt", -1)], {}),
    # Expiry is derived at read time, so every open-job read carries a deadline
    # range: open if the field is absent/null, or if it is still in the future.
    # This index serves that branch, and `make db-explain` shows which of the
    # two branches of the `$or` it actually picks.
    ("jobs", [("status", 1), ("deadline", 1)], {}),
    ("jobs", [("location", 1)], {}),
    ("jobs", [("employmentType", 1)], {}),
    ("jobs", [("experienceLevel", 1)], {}),
    ("jobs", [("remote", 1)], {}),
    ("applications", [("jobId", 1), ("candidateId", 1)], {"unique": True}),
    ("applications", [("candidateId", 1)], {}),
    ("applications", [("jobId", 1)], {}),
    # Employer funnel filters by job *and* stage.
    ("applications", [("jobId", 1), ("status", 1)], {}),
    ("applications", [("candidateId", 1), ("status", 1)], {}),
    ("matchResults", [("applicationId", 1)], {"unique": True}),
    # One cached ranking per candidate; the unique index is what lets the
    # recommender upsert instead of racing a read-then-write on dashboard loads.
    ("candidateRecommendations", [("candidateId", 1)], {"unique": True}),
)

# Short server-selection timeout so health checks (and failing DBs) resolve
# quickly instead of hanging on slow Atlas network conditions.
_PING_TIMEOUT_MS = 1500


def get_db() -> Database:
    """Lazily obtain a reusable MongoClient and the configured database.

    `connect=False` prevents any network I/O until a real operation runs, so
    importing the app never requires the database to be reachable.
    """
    global _client
    if _client is None:
        _client = MongoClient(
            current_app.config["MONGO_URI"],
            connect=False,
            serverSelectionTimeoutMS=_PING_TIMEOUT_MS,
        )
    return _client[current_app.config["MONGO_DB_NAME"]]


def ping_db() -> None:
    """Run a lightweight round-trip against the configured database."""
    get_db().command("ping")


def ensure_indexes() -> None:
    """Create the indexes the application relies on. Idempotent."""
    db = get_db()
    for collection, keys, options in INDEX_SPECS:
        db[collection].create_index(keys, **options)
