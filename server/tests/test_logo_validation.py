"""Company-logo validation edge cases.

Exercises ``logo_service.validate_logo`` against crafted byte payloads: the 1MB
cap, wrong MIME types, empty files, and the three accepted formats. The SVG case
matters most — it is the one script-capable format we accept, so it has to be
sniffed reliably rather than trusted from the filename.

The payloads are real file signatures, not arbitrary bytes: libmagic decides
what these are, so a test that did not begin with a genuine header would pass or
fail for the wrong reason.
"""

import pytest

from app.services.logo_service import MAX_LOGO_BYTES, mimetype_for_logo, validate_logo
from app.utils.errors import ValidationError

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)

JPEG_1PX = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000"
    "ffdb004300ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    "ffc0000b080001000101011100ffc40014000100000000000000000000000000000009ffda0008010100003f00"
    "d2cf20ffd9"
)

WEBP_1PX = (
    b"RIFF\x24\x00\x00\x00WEBPVP8L\x0d\x00\x00\x00\x2f\x00\x00\x00\x00\x07\x10\x11\x11\x88\x88\xfe"
    b"\x07\x00"
)

SVG_WITH_PROLOG = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40">'
    b'<rect width="40" height="40" fill="#8a3413"/></svg>'
)

SVG_BARE = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="4"/></svg>'


class Storage:
    """Minimal stand-in for Flask's ``FileStorage``: only ``.read()`` is used."""

    def __init__(self, data: bytes, filename: str = "logo"):
        self.data = data
        self.filename = filename

    def read(self):
        return self.data


def expect_rejected(payload: bytes, expected_code: str) -> ValidationError:
    with pytest.raises(ValidationError) as excinfo:
        validate_logo(Storage(payload))
    assert excinfo.value.code == expected_code
    assert excinfo.value.status == 422
    return excinfo.value


def test_png_accepted():
    assert validate_logo(Storage(PNG_1PX, "logo.png")) == PNG_1PX


def test_jpeg_accepted():
    assert validate_logo(Storage(JPEG_1PX, "logo.jpg")) == JPEG_1PX


def test_webp_accepted():
    assert validate_logo(Storage(WEBP_1PX, "logo.webp")) == WEBP_1PX


def test_svg_with_xml_prolog_accepted():
    assert validate_logo(Storage(SVG_WITH_PROLOG, "logo.svg")) == SVG_WITH_PROLOG


def test_svg_without_prolog_accepted():
    assert validate_logo(Storage(SVG_BARE, "logo.svg")) == SVG_BARE


def test_oversized_logo_rejected():
    payload = PNG_1PX + b"\x00" * (MAX_LOGO_BYTES + 8)
    error = expect_rejected(payload, "logo_too_large")
    assert "1MB" in error.message


def test_empty_file_rejected():
    error = expect_rejected(b"", "logo_invalid_type")
    assert "empty" in error.message.lower()


def test_plain_text_rejected():
    expect_rejected(b"just some text, not an image", "logo_invalid_type")


def test_gif_rejected():
    payload = b"GIF89a" + b"\x00" * 512
    expect_rejected(payload, "logo_invalid_type")


def test_pdf_rejected():
    expect_rejected(b"%PDF-1.4\n" + b"\x00" * 512, "logo_invalid_type")


def test_svg_extension_without_svg_content_rejected():
    """The filename must never be what makes a file acceptable.

    libmagic reports bare text as ``text/plain``, which is on the SVG
    allowlist precisely because a real SVG with no prolog also reports that way.
    The content check is what separates the two.
    """
    expect_rejected(b"not markup at all, whatever the name says", "logo_invalid_type")


def test_rejection_message_lists_accepted_formats():
    error = expect_rejected(b"nope", "logo_invalid_type")
    detail = error.details[0]["message"]
    for expected in ("PNG", "JPEG", "SVG", "WEBP", "1MB"):
        assert expected in detail


def test_mimetype_maps_every_accepted_extension():
    assert mimetype_for_logo("logo.png") == "image/png"
    assert mimetype_for_logo("logo.JPG") == "image/jpeg"
    assert mimetype_for_logo("logo.jpeg") == "image/jpeg"
    assert mimetype_for_logo("logo.webp") == "image/webp"
    assert mimetype_for_logo("logo.svg") == "image/svg+xml"


def test_mimetype_falls_back_for_unknown_extension():
    assert mimetype_for_logo("logo") == "image/png"
