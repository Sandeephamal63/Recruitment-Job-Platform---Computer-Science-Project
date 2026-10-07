"""Candidate-avatar validation edge cases.

Exercises ``avatar_service.validate_avatar`` against crafted byte payloads: the
1MB cap, wrong MIME types, empty files, and the three accepted formats. The
payloads are real file signatures, not arbitrary bytes, because libmagic decides
what these are.

The SVG cases matter most here, and they are the inverse of the logo suite's:
``logo_service`` accepts SVG (real logos are often vector) and defends it with a
content sniff plus a CSP sandbox header, whereas an avatar is arbitrary content
picked off someone's phone, so SVG is rejected outright. Both directions are
asserted so neither validator is "fixed" to match the other.
"""

import pytest

from app.services.avatar_service import (
    ACCEPTED_COPY,
    MAX_AVATAR_BYTES,
    mimetype_for_avatar,
    validate_avatar,
)
from app.utils.errors import ValidationError
from tests.test_logo_validation import JPEG_1PX, PNG_1PX, WEBP_1PX, Storage

SVG_WITH_PROLOG = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40">'
    b'<rect width="40" height="40" fill="#8a3413"/></svg>'
)

SVG_BARE = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="4"/></svg>'


def expect_rejected(payload: bytes, expected_code: str) -> ValidationError:
    with pytest.raises(ValidationError) as excinfo:
        validate_avatar(Storage(payload))
    assert excinfo.value.code == expected_code
    assert excinfo.value.status == 422
    return excinfo.value


def test_png_accepted():
    assert validate_avatar(Storage(PNG_1PX, "me.png")) == PNG_1PX


def test_jpeg_accepted():
    assert validate_avatar(Storage(JPEG_1PX, "me.jpg")) == JPEG_1PX


def test_webp_accepted():
    assert validate_avatar(Storage(WEBP_1PX, "me.webp")) == WEBP_1PX


def test_svg_rejected():
    """Avatars are raster-only.

    The same payload ``validate_logo`` accepts, refused here. An avatar is
    arbitrary user-uploaded content rather than designed artwork, so the
    script-capable format is not worth the content sniff plus CSP sandbox the
    logo route needs to contain it.
    """
    expect_rejected(SVG_WITH_PROLOG, "avatar_invalid_type")
    expect_rejected(SVG_BARE, "avatar_invalid_type")


def test_svg_named_png_is_rejected():
    """The filename must never be what makes a file acceptable."""
    expect_rejected(SVG_WITH_PROLOG, "avatar_invalid_type")  # .svg name
    with pytest.raises(ValidationError) as excinfo:
        validate_avatar(Storage(SVG_WITH_PROLOG, "avatar.png"))
    assert excinfo.value.code == "avatar_invalid_type"


def test_oversized_avatar_rejected():
    payload = PNG_1PX + b"\x00" * (MAX_AVATAR_BYTES + 8)
    error = expect_rejected(payload, "avatar_too_large")
    assert "1MB" in error.message


def test_empty_file_rejected():
    error = expect_rejected(b"", "avatar_invalid_type")
    assert "empty" in error.message.lower()


def test_plain_text_rejected():
    expect_rejected(b"just some text, not an image", "avatar_invalid_type")


def test_gif_rejected():
    expect_rejected(b"GIF89a" + b"\x00" * 512, "avatar_invalid_type")


def test_pdf_rejected():
    expect_rejected(b"%PDF-1.4\n" + b"\x00" * 512, "avatar_invalid_type")


def test_rejection_message_lists_accepted_formats():
    error = expect_rejected(b"nope", "avatar_invalid_type")
    detail = error.details[0]["message"]
    for expected in ("PNG", "JPEG", "WEBP", "1MB"):
        assert expected in detail
    assert "SVG" not in detail, "the copy must not offer a format the validator refuses"


def test_accepted_copy_matches_the_accepted_formats():
    assert ACCEPTED_COPY == "Avatar must be a PNG, JPEG or WEBP image under 1MB"


def test_mimetype_maps_every_accepted_extension():
    assert mimetype_for_avatar("me.png") == "image/png"
    assert mimetype_for_avatar("me.jpg") == "image/jpeg"
    assert mimetype_for_avatar("me.jpeg") == "image/jpeg"
    assert mimetype_for_avatar("me.webp") == "image/webp"
    assert mimetype_for_avatar("me.PNG") == "image/png"


def test_mimetype_falls_back_for_unknown_extension():
    assert mimetype_for_avatar("me") == "image/png"
    assert mimetype_for_avatar("") == "image/png"
