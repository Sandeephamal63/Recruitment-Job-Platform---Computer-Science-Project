"""The public, candidate-facing snapshot of the company behind a job.

Was previously built inline by two near-identical private ``_attach_employers``
methods (``JobService`` and ``ApplicationService``). Both assembled the same six
fields from the same user document, which meant every addition had to be made
twice and the two summaries could silently drift apart. One builder, two callers.
"""

from ..utils.urls import company_logo_url_for


def build_employer_summary(employer: dict) -> dict:
    """Public employer shape attached to jobs and applications at read time.

    ``companyLogoUrl`` is ``None`` when the employer has not uploaded a logo,
    which is the signal the client uses to fall back to an initials badge.
    """
    employer_id = str(employer["_id"])
    return {
        "id": employer_id,
        "name": employer.get("name"),
        "companyName": employer.get("companyName") or employer.get("name"),
        "companyDescription": employer.get("companyDescription") or "",
        "companySize": employer.get("companySize") or "",
        "companyIndustry": employer.get("companyIndustry") or "",
        "companyLogoUrl": company_logo_url_for(employer, employer_id),
    }
