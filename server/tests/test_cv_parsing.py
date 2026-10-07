"""CV parsing edge cases (M6-mandated).

Exercises ``cv_service.validate_and_parse`` against crafted byte payloads: the
5MB cap, wrong MIME types, empty files, a valid DOCX (built in-memory as a
minimal zip) and a PDF header with no extractable text. All malformed inputs
must raise ``422`` with a specific, actionable message.
"""
import io
import zipfile

import pytest

from app.services.cv_service import MAX_CV_BYTES, validate_and_parse
from app.utils.errors import ValidationError

DOCX_DOCUMENT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body><w:p><w:r><w:t>Python Flask experience five years.</w:t></w:r>"
    "</w:p></w:body></w:document>"
)


class Storage:
    """Minimal stand-in for Flask's ``FileStorage``: only ``.read()`` is used."""

    def __init__(self, data: bytes):
        self.data = data

    def read(self):
        return self.data


def make_docx(text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        document = DOCX_DOCUMENT.replace("Python Flask experience five years.", text)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def expect_rejected(payload: bytes, expected_code: str) -> ValidationError:
    with pytest.raises(ValidationError) as excinfo:
        validate_and_parse(Storage(payload))
    assert excinfo.value.code == expected_code
    assert excinfo.value.status == 422
    return excinfo.value


def test_valid_docx_extracts_text():
    raw = make_docx("Python Flask experience five years.")
    cv_bytes, text = validate_and_parse(Storage(raw))
    assert cv_bytes == raw
    assert "Python" in text and "Flask" in text


def test_oversized_cv_rejected():
    payload = b"%PDF-1.4\n" + b"\x00" * (MAX_CV_BYTES + 8)
    error = expect_rejected(payload, "cv_too_large")
    assert "5MB" in error.message


def test_empty_file_rejected():
    error = expect_rejected(b"", "cv_invalid_type")
    assert "empty" in error.message.lower()


def test_plain_text_rejected():
    expect_rejected(b"hello world, not a cv file", "cv_invalid_type")


def test_jpeg_rejected():
    expect_rejected(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 512, "cv_invalid_type")


def test_corrupt_pdf_raises_clear_parse_error():
    payload = b"%PDF-1.4\n" + b"\x00garbage\xffnot-a-pdf-stream" * 64
    error = expect_rejected(payload, "cv_parse_failed")
    assert "valid PDF or DOCX" in error.message