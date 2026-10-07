"""Public URL shapes.

Lives under ``utils`` rather than in a service or schema because both of those
layers need it: the employer summary that ships with every job is assembled in
``app.services.employer_summary``, while ``ProfileSchema`` and
``EmployerSummarySchema`` serialise the same field. Importing it from either
side would otherwise create a cycle (schemas -> services -> job_service ->
schemas). Keeping it here, importing nothing, makes one definition of the path
that all three can share.
"""

COMPANY_LOGO_PATH = "profile/employers/{employer_id}/logo"


def company_logo_url(employer_id: str) -> str:
    """Public logo URL, relative to the API root (no leading slash).

    Relative rather than absolute so the client can prefix whichever base URL it
    is configured with, and so the value is identical no matter which host serves
    the API.
    """
    return COMPANY_LOGO_PATH.format(employer_id=employer_id)


def company_logo_url_for(employer: dict, employer_id: str) -> str | None:
    """The same URL, or ``None`` when the employer has uploaded no logo.

    ``None`` is the signal the client uses to fall back to an initials badge
    rather than rendering a broken image.
    """
    return company_logo_url(employer_id) if employer.get("logoFileRef") else None
