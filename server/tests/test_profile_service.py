"""Profile service rules at the service layer (self-service fields, the
reusable profile CV, the employer company logo, the candidate avatar, and saved
jobs) driven by in-memory repository fakes."""
from bson import ObjectId

import pytest

from app.services.profile_service import MAX_SAVED_JOBS, ProfileService
from app.utils.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from tests.fakes import (
    FakeApplicationRepository,
    FakeAvatarRepository,
    FakeCVRepository,
    FakeJobRepository,
    FakeLogoRepository,
    FakeUserRepository,
)
from tests.test_logo_validation import PNG_1PX, Storage


class FakeUpload:
    """Stands in for the Werkzeug FileStorage the route hands the service."""

    def __init__(self, filename: str):
        self.filename = filename


def make_service(*, users=None, jobs=None, logos=None, applications=None, avatars=None):
    return ProfileService(
        users=FakeUserRepository(users),
        cvs=FakeCVRepository(),
        jobs=FakeJobRepository(jobs),
        logos=logos if logos is not None else FakeLogoRepository(),
        applications=FakeApplicationRepository(applications),
        avatars=avatars if avatars is not None else FakeAvatarRepository(),
    )


def candidate_doc(**extra):
    return {
        "_id": ObjectId(),
        "role": "candidate",
        "name": "Priya Raman",
        "email": "priya@example.dev",
        "headline": "Frontend Developer",
        "skills": ["React"],
        **extra,
    }


def employer_doc(**extra):
    return {
        "_id": ObjectId(),
        "role": "employer",
        "name": "Dana Okafor",
        "email": "dana@acme.dev",
        "companyName": "Acme",
        **extra,
    }


def job_doc(*, status="open", title="Frontend Developer"):
    return {
        "_id": ObjectId(),
        "title": title,
        "status": status,
        "createdAt": None,
    }


def test_update_profile_stamps_updated_at():
    user = candidate_doc()
    service = make_service(users=[user])

    updated = service.update_profile(str(user["_id"]), {"headline": "Senior Frontend Engineer"})

    assert updated["headline"] == "Senior Frontend Engineer"
    assert updated["updatedAt"] is not None


def test_update_profile_with_no_fields_is_a_no_op():
    user = candidate_doc()
    service = make_service(users=[user])

    result = service.update_profile(str(user["_id"]), {})

    assert result["_id"] == user["_id"]


def test_update_profile_rejects_unknown_user():
    service = make_service()

    with pytest.raises(NotFoundError) as excinfo:
        service.update_profile(str(ObjectId()), {"headline": "Anything"})
    assert excinfo.value.code == "user_not_found"


def test_employer_cannot_store_a_profile_cv():
    employer = {"_id": ObjectId(), "role": "employer", "name": "Acme", "email": "h@acme.dev"}
    service = make_service(users=[employer])

    with pytest.raises(ConflictError) as excinfo:
        service.upload_cv(str(employer["_id"]), FakeUpload("cv.pdf"))
    assert excinfo.value.code == "profile_cv_not_supported"


def test_download_cv_without_a_profile_cv_is_not_found():
    user = candidate_doc()
    service = make_service(users=[user])

    with pytest.raises(NotFoundError) as excinfo:
        service.download_cv(str(user["_id"]))
    assert excinfo.value.code == "profile_cv_missing"


def test_delete_cv_clears_the_reference():
    user = candidate_doc(cvFileRef=ObjectId(), cvFileName="cv.pdf", cvParsedText="Python")
    service = make_service(users=[user])

    updated = service.delete_cv(str(user["_id"]))

    assert updated["cvFileRef"] is None
    assert updated["cvFileName"] is None
    assert updated["cvParsedText"] is None


def test_saving_the_same_job_twice_is_idempotent():
    user = candidate_doc()
    job = job_doc()
    service = make_service(users=[user], jobs=[job])

    service.save_job(str(user["_id"]), str(job["_id"]))
    result = service.save_job(str(user["_id"]), str(job["_id"]))

    assert len(result["savedJobIds"]) == 1


def test_cannot_save_a_closed_job():
    user = candidate_doc()
    job = job_doc(status="closed")
    service = make_service(users=[user], jobs=[job])

    with pytest.raises(NotFoundError) as excinfo:
        service.save_job(str(user["_id"]), str(job["_id"]))
    assert excinfo.value.code == "job_not_found"


def test_saved_jobs_reaches_the_documented_cap():
    user = candidate_doc(savedJobIds=[ObjectId() for _ in range(MAX_SAVED_JOBS)])
    spare = job_doc()
    service = make_service(users=[user], jobs=[spare])

    with pytest.raises(ConflictError) as excinfo:
        service.save_job(str(user["_id"]), str(spare["_id"]))
    assert excinfo.value.code == "saved_jobs_limit_reached"


def test_unsave_accepts_a_malformed_id_without_a_crash():
    user = candidate_doc(savedJobIds=[])
    service = make_service(users=[user])

    with pytest.raises(NotFoundError) as excinfo:
        service.remove_saved_job(str(user["_id"]), "not-an-object-id")
    assert excinfo.value.code == "job_not_found"


def test_list_saved_jobs_keeps_saved_order_and_skips_deleted_jobs():
    first, second, gone = job_doc(title="First"), job_doc(title="Second"), job_doc(title="Gone")
    user = candidate_doc(savedJobIds=[second["_id"], gone["_id"], first["_id"]])
    service = make_service(users=[user], jobs=[first, second])

    titles = [job["title"] for job in service.list_saved_jobs(str(user["_id"]))]

    assert titles == ["Second", "First"]


def test_employer_can_upload_a_company_logo():
    employer = employer_doc()
    logos = FakeLogoRepository()
    service = make_service(users=[employer], logos=logos)

    result = service.upload_company_logo(str(employer["_id"]), Storage(PNG_1PX, "acme.png"))

    assert result["companyLogoFileName"] == "acme.png"
    assert result["companyLogoUrl"] == f"profile/employers/{employer['_id']}/logo"
    assert logos.deleted == []


def test_the_public_logo_url_is_stable_across_uploads():
    """The URL is derived from the employer, not from the file, so it always
    serves whatever logo is current. A client that cached it stays correct after
    the employer replaces their logo."""
    employer = employer_doc()
    logos = FakeLogoRepository()
    service = make_service(users=[employer], logos=logos)

    first = service.upload_company_logo(str(employer["_id"]), Storage(PNG_1PX, "old.png"))
    second = service.upload_company_logo(str(employer["_id"]), Storage(PNG_1PX, "new.png"))

    assert second["companyLogoFileName"] == "new.png"
    assert second["companyLogoUrl"] == first["companyLogoUrl"]
    assert service.download_company_logo(str(employer["_id"]))[1] == "new.png"


def test_replacing_a_logo_deletes_the_superseded_bytes():
    employer = employer_doc()
    logos = FakeLogoRepository()
    service = make_service(users=[employer], logos=logos)
    service.upload_company_logo(str(employer["_id"]), Storage(PNG_1PX, "old.png"))
    superseded = logos.ref_named("old.png")

    service.upload_company_logo(str(employer["_id"]), Storage(PNG_1PX, "new.png"))

    assert logos.deleted == [superseded]


def test_a_rejected_upload_leaves_the_existing_logo_untouched():
    """The old bytes are only dropped once the new write has succeeded, so a
    failed upload costs the employer nothing."""
    employer = employer_doc()
    logos = FakeLogoRepository()
    service = make_service(users=[employer], logos=logos)
    service.upload_company_logo(str(employer["_id"]), Storage(PNG_1PX, "good.png"))
    stored_ref = logos.ref_named("good.png")

    with pytest.raises(ValidationError) as excinfo:
        service.upload_company_logo(str(employer["_id"]), Storage(b"not an image", "bad.png"))
    assert excinfo.value.code == "logo_invalid_type"

    assert logos.deleted == []
    assert stored_ref in logos.filenames
    assert service.download_company_logo(str(employer["_id"]))[1] == "good.png"


def test_candidate_cannot_store_a_company_logo():
    """The role rule is enforced in the service, not only on the route."""
    candidate = candidate_doc()
    service = make_service(users=[candidate])

    with pytest.raises(ConflictError) as excinfo:
        service.upload_company_logo(str(candidate["_id"]), Storage(PNG_1PX, "logo.png"))
    assert excinfo.value.code == "company_logo_not_supported"


def test_download_company_logo_is_reachable_without_ownership():
    """The landing page's employer strip renders for signed-out visitors, so the
    read is deliberately not owner-scoped — it exposes bytes and nothing else."""
    employer = employer_doc()
    logos = FakeLogoRepository()
    service = make_service(users=[employer], logos=logos)
    service.upload_company_logo(str(employer["_id"]), Storage(PNG_1PX, "acme.png"))

    content, filename = service.download_company_logo(str(employer["_id"]))

    assert content == PNG_1PX
    assert filename == "acme.png"


def test_download_company_logo_without_one_is_not_found():
    employer = employer_doc()
    service = make_service(users=[employer])

    with pytest.raises(NotFoundError) as excinfo:
        service.download_company_logo(str(employer["_id"]))
    assert excinfo.value.code == "company_logo_missing"


def test_delete_company_logo_clears_the_reference_and_bytes():
    employer = employer_doc()
    logos = FakeLogoRepository()
    service = make_service(users=[employer], logos=logos)
    service.upload_company_logo(str(employer["_id"]), Storage(PNG_1PX, "acme.png"))

    updated = service.delete_company_logo(str(employer["_id"]))

    assert updated["logoFileRef"] is None
    assert updated["logoFileName"] is None
    assert len(logos.deleted) == 1


def application_doc(*, job_id, candidate_id, status="submitted"):
    return {
        "_id": ObjectId(),
        "jobId": job_id,
        "candidateId": candidate_id,
        "status": status,
    }


def avatar_scene(**extra):
    """An employer, a candidate with an avatar, a job the employer owns, and an
    application joining them — the minimum for the employer-side read."""
    employer = employer_doc()
    candidate = candidate_doc()
    job = job_doc()
    job["employerId"] = employer["_id"]
    application = application_doc(job_id=job["_id"], candidate_id=candidate["_id"])
    scene = {
        "users": [employer, candidate],
        "jobs": [job],
        "applications": [application],
    }
    scene.update(extra)
    return scene


def test_candidate_can_upload_an_avatar():
    candidate = candidate_doc()
    avatars = FakeAvatarRepository()
    service = make_service(users=[candidate], avatars=avatars)

    result = service.upload_avatar(str(candidate["_id"]), Storage(PNG_1PX, "me.png"))

    assert result == {"avatarFileName": "me.png"}
    assert avatars.ref_named("me.png")
    assert avatars.deleted == []


def test_upload_avatar_persists_the_reference_and_filename():
    candidate = candidate_doc()
    avatars = FakeAvatarRepository()
    service = make_service(users=[candidate], avatars=avatars)

    service.upload_avatar(str(candidate["_id"]), Storage(PNG_1PX, "me.png"))

    stored = service.get_profile(str(candidate["_id"]))
    assert stored["avatarFileName"] == "me.png"
    assert stored["avatarFileRef"] == avatars.ref_named("me.png")


def test_replacing_an_avatar_deletes_the_superseded_bytes():
    candidate = candidate_doc()
    avatars = FakeAvatarRepository()
    service = make_service(users=[candidate], avatars=avatars)
    service.upload_avatar(str(candidate["_id"]), Storage(PNG_1PX, "old.png"))
    superseded = avatars.ref_named("old.png")

    service.upload_avatar(str(candidate["_id"]), Storage(PNG_1PX, "new.png"))

    assert avatars.deleted == [superseded]
    assert service.download_avatar(str(candidate["_id"]))[1] == "new.png"


def test_a_rejected_avatar_leaves_the_existing_one_untouched():
    """The old bytes are only dropped once the new write has succeeded, so a
    failed upload costs the candidate nothing."""
    candidate = candidate_doc()
    avatars = FakeAvatarRepository()
    service = make_service(users=[candidate], avatars=avatars)
    service.upload_avatar(str(candidate["_id"]), Storage(PNG_1PX, "good.png"))
    stored_ref = avatars.ref_named("good.png")

    with pytest.raises(ValidationError) as excinfo:
        service.upload_avatar(str(candidate["_id"]), Storage(b"not an image", "bad.png"))
    assert excinfo.value.code == "avatar_invalid_type"

    assert avatars.deleted == []
    assert stored_ref in avatars.filenames
    assert service.download_avatar(str(candidate["_id"]))[1] == "good.png"


def test_avatar_upload_does_not_invalidate_the_recommendation_cache():
    """An avatar is not text.

    ``profileUpdatedAt`` and ``profileEmbedding`` describe the text the
    recommender ranks a candidate on. Replacing a photo must leave both alone,
    or every avatar change would throw away a cached ranking and force a
    re-encode of a CV that never changed.
    """
    candidate = candidate_doc(
        profileUpdatedAt="stamp", profileEmbedding="vector", profileEmbeddingModel="model-v1"
    )
    service = make_service(users=[candidate])

    service.upload_avatar(str(candidate["_id"]), Storage(PNG_1PX, "me.png"))

    stored = service.get_profile(str(candidate["_id"]))
    assert stored["profileUpdatedAt"] == "stamp"
    assert stored["profileEmbedding"] == "vector"
    assert stored["profileEmbeddingModel"] == "model-v1"
    assert stored["updatedAt"] is not None, "updatedAt still moves; only the recommender stamp is spared"


def test_employer_cannot_store_an_avatar():
    """The role rule is enforced in the service, not only on the route."""
    employer = employer_doc()
    service = make_service(users=[employer])

    with pytest.raises(ConflictError) as excinfo:
        service.upload_avatar(str(employer["_id"]), Storage(PNG_1PX, "me.png"))
    assert excinfo.value.code == "avatar_not_supported"


def test_employer_cannot_read_an_avatar_through_the_owner_route():
    employer = employer_doc()
    service = make_service(users=[employer])

    with pytest.raises(ConflictError) as excinfo:
        service.download_avatar(str(employer["_id"]))
    assert excinfo.value.code == "avatar_not_supported"


def test_download_own_avatar_returns_the_stored_bytes():
    candidate = candidate_doc()
    avatars = FakeAvatarRepository()
    service = make_service(users=[candidate], avatars=avatars)
    service.upload_avatar(str(candidate["_id"]), Storage(PNG_1PX, "me.png"))

    content, filename = service.download_avatar(str(candidate["_id"]))

    assert content == PNG_1PX
    assert filename == "me.png"


def test_download_own_avatar_without_one_is_not_found():
    candidate = candidate_doc()
    service = make_service(users=[candidate])

    with pytest.raises(NotFoundError) as excinfo:
        service.download_avatar(str(candidate["_id"]))
    assert excinfo.value.code == "avatar_missing"


def test_delete_avatar_clears_the_reference_and_bytes():
    candidate = candidate_doc()
    avatars = FakeAvatarRepository()
    service = make_service(users=[candidate], avatars=avatars)
    service.upload_avatar(str(candidate["_id"]), Storage(PNG_1PX, "me.png"))

    updated = service.delete_avatar(str(candidate["_id"]))

    assert updated["avatarFileRef"] is None
    assert updated["avatarFileName"] is None
    assert len(avatars.deleted) == 1


def test_employer_can_read_the_avatar_of_an_applicant_to_their_job():
    scene = avatar_scene()
    employer = scene["users"][0]
    candidate = scene["users"][1]
    application = scene["applications"][0]
    avatars = FakeAvatarRepository()
    service = make_service(users=scene["users"], jobs=scene["jobs"],
                           applications=scene["applications"], avatars=avatars)
    service.upload_avatar(str(candidate["_id"]), Storage(PNG_1PX, "me.png"))

    content, filename = service.download_candidate_avatar(
        str(employer["_id"]), str(application["_id"])
    )

    assert content == PNG_1PX
    assert filename == "me.png"


def test_employer_cannot_read_an_avatar_from_another_employers_job():
    """The whole point of keying the read on the application: an employer sees
    the people who applied to their postings, not every candidate on the site."""
    scene = avatar_scene()
    owner = scene["users"][0]
    candidate = scene["users"][1]
    application = scene["applications"][0]
    intruder = employer_doc(email="intruder@other.dev")
    avatars = FakeAvatarRepository()
    service = make_service(users=[*scene["users"], intruder], jobs=scene["jobs"],
                           applications=scene["applications"], avatars=avatars)
    service.upload_avatar(str(candidate["_id"]), Storage(PNG_1PX, "me.png"))

    with pytest.raises(ForbiddenError):
        service.download_candidate_avatar(str(intruder["_id"]), str(application["_id"]))

    assert service.download_candidate_avatar(str(owner["_id"]), str(application["_id"]))


def test_candidate_avatar_read_rejects_an_unknown_application():
    scene = avatar_scene()
    employer = scene["users"][0]
    service = make_service(users=scene["users"], jobs=scene["jobs"], applications=scene["applications"])

    with pytest.raises(NotFoundError) as excinfo:
        service.download_candidate_avatar(str(employer["_id"]), str(ObjectId()))
    assert excinfo.value.code == "application_not_found"


def test_candidate_avatar_read_404s_when_the_applicant_has_no_avatar():
    scene = avatar_scene()
    employer = scene["users"][0]
    application = scene["applications"][0]
    service = make_service(users=scene["users"], jobs=scene["jobs"], applications=scene["applications"])

    with pytest.raises(NotFoundError) as excinfo:
        service.download_candidate_avatar(str(employer["_id"]), str(application["_id"]))
    assert excinfo.value.code == "avatar_missing"
