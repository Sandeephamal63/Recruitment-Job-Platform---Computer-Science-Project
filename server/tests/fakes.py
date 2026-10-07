"""In-memory repository fakes for service-layer tests (AGENTS: service tests
use fake/in-memory repositories — list-backed, matching method signatures —
never mongomock or a live database)."""
from bson import ObjectId

from app.repositories.job_repository import open_job_filter
from app.utils.time import utcnow


class MemoryStore:
    """Stores documents by a ``_id`` ObjectId; supports the small read-only /
    single-write surfaces the service layer exercises."""

    def __init__(self, docs: list[dict] | None = None):
        self._docs: list[dict] = [dict(doc) for doc in (docs or [])]

    def _find(self, key: str, value) -> dict | None:
        for doc in self._docs:
            if doc.get(key) == value:
                return dict(doc)
        return None

    def _find_by_id(self, doc_id: str) -> dict | None:
        oid = self._oid(doc_id)
        if oid is None:
            return None
        return self._find("_id", oid)

    def insert(self, doc: dict) -> ObjectId:
        doc = dict(doc)
        doc.setdefault("_id", ObjectId())
        self._docs.append(dict(doc))
        return doc["_id"]

    def _replace(self, doc_id: str, updates: dict) -> dict | None:
        """Apply a ``$set``-style update in place, as the real repositories do."""
        target = self._oid(doc_id)
        for index, doc in enumerate(self._docs):
            if doc.get("_id") == target:
                self._docs[index] = {**doc, **updates}
                return dict(self._docs[index])
        return None

    def _where(self, predicate) -> list[dict]:
        return [dict(doc) for doc in self._docs if predicate(doc)]

    @staticmethod
    def _oid(value: str) -> ObjectId | None:
        try:
            return ObjectId(value)
        except Exception:
            return None


class FakeUserRepository:
    def __init__(self, users: list[dict] | None = None):
        self._store = MemoryStore(users)

    def insert(self, doc: dict) -> str:
        return str(self._store.insert(doc))

    def find_by_ids(self, user_ids: list[str]) -> list[dict]:
        return [dict(doc) for doc in self._store._docs if str(doc["_id"]) in set(user_ids)]

    def find_by_id(self, user_id: str) -> dict | None:
        return self._store._find_by_id(user_id)

    def find_profile_embedding(self, user_id: str) -> dict | None:
        user = self._store._find_by_id(user_id)
        if not user:
            return None
        return {
            key: user.get(key)
            for key in (
                "profileEmbedding",
                "profileEmbeddingModel",
                "profileUpdatedAt",
                "createdAt",
            )
        }

    def find_by_email(self, email: str) -> dict | None:
        return self._store._find("email", email)

    def update(self, user_id: str, updates: dict) -> dict | None:
        return self._store._replace(user_id, updates)

    def add_saved_job(self, user_id: str, job_id: ObjectId) -> dict | None:
        saved = self._store._find_by_id(user_id) or {}
        existing = list(saved.get("savedJobIds") or [])
        if job_id not in existing:
            existing.append(job_id)
        return self._store._replace(user_id, {"savedJobIds": existing})

    def remove_saved_job(self, user_id: str, job_id: ObjectId) -> dict | None:
        saved = self._store._find_by_id(user_id) or {}
        remaining = [oid for oid in (saved.get("savedJobIds") or []) if oid != job_id]
        return self._store._replace(user_id, {"savedJobIds": remaining})


class FakeJobRepository:
    def __init__(self, jobs: list[dict] | None = None):
        self._store = MemoryStore(jobs)

    def insert(self, doc: dict) -> str:
        return str(self._store.insert(doc))

    def find_by_id(self, job_id: str) -> dict | None:
        return self._store._find_by_id(job_id)

    def find_by_ids(self, job_ids: list[str]) -> list[dict]:
        wanted = set(job_ids)
        return [dict(doc) for doc in self._store._docs if str(doc["_id"]) in wanted]

    def find_by_employer(self, employer_id: str) -> list[dict]:
        oid = ObjectId(employer_id)
        return [dict(doc) for doc in self._store._docs if doc.get("employerId") == oid]

    def find_open_with_embeddings(self, now=None) -> list[dict]:
        """Mirrors the real ``find_open_with_embeddings``.

        It imports ``open_job_filter`` rather than re-spelling the open/expired
        rule, so the fake evaluates the *actual* Mongo query and a change to the
        predicate can never leave the tests asserting against a stale copy.
        """
        return [
            dict(doc)
            for doc in self._store._docs
            if self._matches_query(doc, open_job_filter(now))
        ]

    def update(self, job_id: str, updates: dict) -> dict | None:
        return self._store._replace(job_id, updates)

    def page_open(
        self, query: dict, sort: str, page: int, page_size: int, now=None
    ) -> tuple[list[dict], int]:
        """Filter/sort in Python, mirroring the aggregate's contract."""
        matched = self._matching({**open_job_filter(now), **query})
        if sort == "oldest":
            matched.sort(key=lambda doc: doc.get("createdAt"))
        elif sort == "title":
            matched.sort(key=lambda doc: doc.get("title", ""))
        else:
            matched.sort(key=lambda doc: doc.get("createdAt"), reverse=True)
        start = (page - 1) * page_size
        return matched[start : start + page_size], len(matched)

    def _matching(self, query: dict) -> list[dict]:
        return [
            dict(doc)
            for doc in self._store._docs
            if self._matches_query(doc, query)
        ]

    @staticmethod
    def _matches_query(doc: dict, query: dict) -> bool:
        for key, expected in query.items():
            if key == "$and":
                # Used by the browse text search, which nests its own ``$or`` so
                # it does not collide with the top-level expiry clause.
                if not all(FakeJobRepository._matches_query(doc, clause) for clause in expected):
                    return False
            elif key == "$or":
                if not any(_matches_term(doc, term) for term in expected):
                    return False
            elif not _matches_term(doc, {key: expected}):
                return False
        return True


def _matches_term(doc: dict, term: dict) -> bool:
    for key, expected in term.items():
        value = doc.get(key)
        if key == "requiredSkills" and isinstance(expected, dict):
            if "$all" in expected and not set(expected["$all"]) <= set(value or []):
                return False
            continue
        if isinstance(expected, dict) and "$gte" in expected:
            if value is None or value < expected["$gte"]:
                return False
            continue
        if hasattr(expected, "pattern"):
            if value is None or not expected.search(value):
                return False
            continue
        if value != expected:
            return False
    return True


class FakeApplicationRepository:
    def __init__(self, applications: list[dict] | None = None):
        self._store = MemoryStore(applications)
        self._scores: dict[str, int] = {}

    def create(self, doc: dict, session=None) -> str:
        return str(self._store.insert(doc))

    def find_by_id(self, application_id: str) -> dict | None:
        return self._store._find_by_id(application_id)

    def find_by_candidate(self, candidate_id: str) -> list[dict]:
        return [dict(doc) for doc in self._store._docs if str(doc.get("candidateId")) == candidate_id]

    def find_by_job(self, job_id: str) -> list[dict]:
        return [dict(doc) for doc in self._store._docs if str(doc.get("jobId")) == job_id]

    def find_by_duplicate(self, job_id: str, candidate_id: str) -> dict | None:
        for doc in self._store._docs:
            if doc.get("jobId") == ObjectId(job_id) and doc.get("candidateId") == ObjectId(candidate_id):
                return dict(doc)
        return None

    def find_duplicate(self, job_id: str, candidate_id: str) -> dict | None:
        return self.find_by_duplicate(job_id, candidate_id)

    def update_status(self, application_id: str, status: str, now, rejection_reason=None) -> dict:
        updates: dict = {"status": status, "updatedAt": now}
        if rejection_reason is not None:
            updates["rejectionReason"] = rejection_reason
        elif status != "rejected":
            updates["rejectionReason"] = None
        return self._store._replace(application_id, updates) or {}

    def update_status_many(self, application_ids: list[str], status: str, now, rejection_reason=None):
        return [
            self.update_status(application_id, status, now, rejection_reason)
            for application_id in application_ids
        ]

    def add_note(self, application_id: str, note: dict) -> dict | None:
        existing = self._store._find_by_id(application_id) or {}
        updated = self._store._replace(
            application_id,
            {"notes": list(existing.get("notes") or []) + [note], "updatedAt": note["createdAt"]},
        )
        return updated

    def remove_note(self, application_id: str, note_id: str) -> dict | None:
        existing = self._store._find_by_id(application_id) or {}
        oid = ObjectId(note_id)
        remaining = [n for n in (existing.get("notes") or []) if n.get("id") != oid]
        return self._store._replace(application_id, {"notes": remaining})

    def page_for_job(self, job_id, status=None, min_score=None, sort="newest", page=1, page_size=25):
        """Filter/sort/page in Python against the scores the fake was given."""
        rows = self.find_by_job(job_id)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if min_score is not None:
            rows = [
                row
                for row in rows
                if (self._scores.get(str(row["_id"])) or 0) >= min_score
            ]
        rows.sort(key=lambda row: row.get("submittedAt"), reverse=sort == "newest")
        if sort in {"score-desc", "score-asc"}:
            rows.sort(
                key=lambda row: self._scores.get(str(row["_id"])) or 0,
                reverse=sort == "score-desc",
            )
        start = (page - 1) * page_size
        return rows[start : start + page_size], len(rows)

    def set_score(self, application_id: str, score: int) -> None:
        """Test-only hook: the real pipeline persists scores in ``matchResults``."""
        self._scores[application_id] = score

    def funnel_by_job(self, job_ids: list[str]) -> dict[str, dict[str, int]]:
        wanted = set(job_ids)
        funnel: dict[str, dict[str, int]] = {job_id: {} for job_id in job_ids}
        for doc in self._store._docs:
            job_id = str(doc.get("jobId"))
            if job_id in wanted:
                funnel[job_id][doc["status"]] = funnel[job_id].get(doc["status"], 0) + 1
        return funnel

    def counts_by_job(self, job_ids: list[str]) -> dict[str, int]:
        return {
            job_id: sum(stages.values())
            for job_id, stages in self.funnel_by_job(job_ids).items()
        }

    def average_score(self, job_ids: list[str]) -> float | None:
        wanted = set(job_ids)
        scores = [
            score
            for application_id, score in self._scores.items()
            if str(self._store._find_by_id(application_id).get("jobId")) in wanted
        ]
        return round(sum(scores) / len(scores), 1) if scores else None

    def score_distribution(self, job_ids: list[str]) -> list[dict]:
        from app.repositories.application_repository import BOUNDARY_BANDS, PENDING_BAND_LABEL

        counts: dict = {}
        for application_id, score in self._scores.items():
            doc = self._store._find_by_id(application_id)
            if str(doc.get("jobId")) not in set(job_ids):
                continue
            band = next(
                (label for bound, label in BOUNDARY_BANDS.items() if score >= bound),
                PENDING_BAND_LABEL,
            )
            counts[band] = counts.get(band, 0) + 1
        return [{"band": band, "count": count} for band, count in counts.items()]


class FakeCVRepository:
    def __init__(self, filenames: dict[str, str] | None = None):
        self._filenames = filenames or {}
        self.deleted: list[str] = []

    def filenames_by_ids(self, file_refs: list[ObjectId]) -> dict[str, str]:
        return {str(ref): self._filenames.get(str(ref)) for ref in file_refs}

    def load(self, file_id: str) -> tuple[bytes, str]:
        return b"", self._filenames.get(str(file_id), "cv")

    def save(self, content: bytes, filename: str) -> str:
        file_id = str(ObjectId())
        self._filenames[file_id] = filename
        return file_id

    def delete(self, file_id: str) -> None:
        self.deleted.append(str(file_id))
        self._filenames.pop(str(file_id), None)


class FakeLogoRepository:
    def __init__(self, filenames: dict[str, str] | None = None, payloads: dict[str, bytes] | None = None):
        self._filenames = filenames or {}
        self._payloads = payloads or {}
        self.deleted: list[str] = []

    @property
    def filenames(self) -> dict[str, str]:
        """Stored filename per file id, so tests can name a ref without reaching
        into the private store."""
        return dict(self._filenames)

    def ref_named(self, filename: str) -> str:
        return next(ref for ref, name in self._filenames.items() if name == filename)

    def load(self, file_id: str) -> tuple[bytes, str]:
        return self._payloads.get(str(file_id), b""), self._filenames.get(str(file_id), "logo")

    def save(self, content: bytes, filename: str) -> str:
        file_id = str(ObjectId())
        self._filenames[file_id] = filename
        self._payloads[file_id] = content
        return file_id

    def delete(self, file_id: str) -> None:
        self.deleted.append(str(file_id))
        self._filenames.pop(str(file_id), None)
        self._payloads.pop(str(file_id), None)


class FakeAvatarRepository:
    """Mirrors ``FakeLogoRepository``; the ``"avatar"`` filename fallback is the
    only behavioural difference, and it exists so a test can tell which
    repository a read came from."""

    def __init__(self, filenames: dict[str, str] | None = None, payloads: dict[str, bytes] | None = None):
        self._filenames = filenames or {}
        self._payloads = payloads or {}
        self.deleted: list[str] = []

    @property
    def filenames(self) -> dict[str, str]:
        return dict(self._filenames)

    def ref_named(self, filename: str) -> str:
        return next(ref for ref, name in self._filenames.items() if name == filename)

    def load(self, file_id: str) -> tuple[bytes, str]:
        return self._payloads.get(str(file_id), b""), self._filenames.get(str(file_id), "avatar")

    def save(self, content: bytes, filename: str) -> str:
        file_id = str(ObjectId())
        self._filenames[file_id] = filename
        self._payloads[file_id] = content
        return file_id

    def delete(self, file_id: str) -> None:
        self.deleted.append(str(file_id))
        self._filenames.pop(str(file_id), None)
        self._payloads.pop(str(file_id), None)


class FakeMatchResultRepository:
    def __init__(self, results: list[dict] | None = None):
        self._store = MemoryStore(results)

    def create_placeholder(self, application_id, now, session=None) -> None:
        self._store.insert(
            {
                "applicationId": application_id,
                "matchScore": None,
                "modelVersion": "pending",
                "createdAt": now,
            }
        )

    def find_by_application(self, application_id: str) -> dict | None:
        for doc in self._store._docs:
            if str(doc.get("applicationId")) == application_id:
                return dict(doc)
        return None

    def find_by_application_ids(self, application_ids: list[str]) -> dict[str, dict]:
        wanted = set(application_ids)
        return {
            str(doc["applicationId"]): dict(doc)
            for doc in self._store._docs
            if str(doc.get("applicationId")) in wanted
        }

    def upsert_result(self, application_id: str, computed: dict) -> None:
        self._store._docs = [d for d in self._store._docs if str(d.get("applicationId")) != application_id]
        self._store.insert(
            {
                "applicationId": ObjectId(application_id),
                "matchScore": computed["matchScore"],
                "matchedSkills": computed["matchedSkills"],
                "missingSkills": computed["missingSkills"],
                "recommendations": computed["recommendations"],
                "modelVersion": computed["modelVersion"],
                "createdAt": utcnow(),
            }
        )

    def reset_to_pending(self, application_ids: list[str]) -> int:
        wanted = set(application_ids)
        changed = 0
        for doc in self._store._docs:
            if str(doc.get("applicationId")) in wanted:
                doc["matchScore"] = None
                doc["modelVersion"] = "pending"
                changed += 1
        return changed


class FakeCandidateRecommendationRepository:
    def __init__(self, rows: list[dict] | None = None):
        self._store = MemoryStore(rows)

    def find_by_candidate(self, candidate_id: str) -> dict | None:
        for doc in self._store._docs:
            if str(doc.get("candidateId")) == candidate_id:
                return dict(doc)
        return None

    def upsert(self, candidate_id: str, recommendations: list[dict], now) -> dict:
        existing = self.find_by_candidate(candidate_id)
        others = [d for d in self._store._docs if str(d.get("candidateId")) != candidate_id]
        self._store._docs = [
            {
                "candidateId": candidate_id,
                "recommendations": recommendations,
                "computedAt": now,
                "createdAt": existing.get("createdAt", now) if existing else now,
            }
        ] + others
        return {"recommendations": recommendations, "computedAt": now}


class FakeRefreshTokenRepository:
    def __init__(self, tokens: list[dict] | None = None):
        self._store = MemoryStore(tokens)

    def create(self, doc: dict) -> str:
        return str(self._store.insert(doc))

    def find_by_token_id(self, token_id: str) -> dict | None:
        return self._store._find("tokenId", token_id)

    def delete_by_token_id(self, token_id: str) -> None:
        self._store._docs = [d for d in self._store._docs if d.get("tokenId") != token_id]

    def delete_by_id(self, token_id) -> None:
        self._store._docs = [d for d in self._store._docs if d.get("_id") != token_id]
