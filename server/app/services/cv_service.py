from typing import Any

import docx2txt
import magic
from pdfminer.high_level import extract_text

from ..utils.errors import ValidationError

MAX_CV_BYTES = 5 * 1024 * 1024
PDF_MIME = "application/pdf"
DOCX_MIMES = {
    "application/zip",
    "application/x-zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_PDF_PAGES = 50


class _InMemoryUpload:
    """Werkzeug file-storage shim.

    Lets already-stored bytes (a candidate's saved profile CV being reused for
    an application) go through the *same* validation and extraction path as a
    fresh upload, so there is exactly one place that decides what counts as a
    parsable CV.
    """

    def __init__(self, data: bytes, filename: str):
        self._data = data
        self.filename = filename

    def read(self) -> bytes:
        return self._data


def upload_from_bytes(data: bytes, filename: str) -> Any:
    return _InMemoryUpload(data, filename)


def mimetype_for(filename: str) -> str:
    """Download-time content type.

    Ingestion sniffs the real type from the bytes; on the way out only the
    stored filename is available, so the extension decides what the browser is
    told it is downloading. Both branches were accepted at upload, so this can
    only ever mislabel a file the user themselves uploaded.
    """
    if (filename or "").lower().endswith(".pdf"):
        return PDF_MIME
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def validate_and_parse(file_storage: Any) -> tuple[bytes, str]:
    """Validate a CV upload and return ``(raw bytes, extracted text)``.

    Content type is sniffed from the bytes (never trusted from the filename);
    because DOCX is a zip archive, a zip-ish signature is accepted and the real
    gate is a successful ``docx2txt`` extraction. Raises a ``422``
    ``ValidationError`` on oversize, wrong type, or parse failure.
    """
    cv_bytes = file_storage.read()

    if len(cv_bytes) > MAX_CV_BYTES:
        raise ValidationError(
            "CV must be under 5MB",
            code="cv_too_large",
            details=[{"field": "cv", "message": "CV must be a PDF or DOCX file under 5MB"}],
        )

    if not cv_bytes:
        raise ValidationError(
            "CV file is empty",
            code="cv_invalid_type",
            details=[{"field": "cv", "message": "CV must be a PDF or DOCX file under 5MB"}],
        )

    detected = magic.from_buffer(cv_bytes, mime=True)
    try:
        if detected == PDF_MIME:
            text = _extract_pdf(cv_bytes)
        elif detected in DOCX_MIMES:
            text = _extract_docx(cv_bytes)
        else:
            raise ValidationError(
                "CV must be a PDF or DOCX file",
                code="cv_invalid_type",
                details=[{"field": "cv", "message": "CV must be a PDF or DOCX file under 5MB"}],
            )
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(
            "CV could not be parsed — please upload a valid PDF or DOCX",
            code="cv_parse_failed",
            details=[
                {"field": "cv", "message": "CV could not be parsed — please upload a valid PDF or DOCX"}
            ],
        ) from exc

    return cv_bytes, text


def _extract_pdf(cv_bytes: bytes) -> str:
    from io import BytesIO

    return (extract_text(BytesIO(cv_bytes), maxpages=MAX_PDF_PAGES) or "").strip()


def _extract_docx(cv_bytes: bytes) -> str:
    from io import BytesIO

    return (docx2txt.process(BytesIO(cv_bytes)) or "").strip()