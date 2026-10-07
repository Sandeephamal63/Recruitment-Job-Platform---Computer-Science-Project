"""Validation for candidate profile-avatar uploads.

Structurally the same shape as :mod:`app.services.logo_service`, but a separate
module because the accepted formats, the size ceiling and the failure codes are
all different — and, more importantly, because an avatar is deliberately
raster-only while a logo is not.

Company logos accept SVG because real logos are frequently vector artwork. An
avatar is not designed artwork: it is arbitrary content a user picked off their
phone or laptop, and SVG is a script-capable format. Restricting the avatar to
PNG/JPEG/WEBP means the bytes cannot carry script at all, which removes the
need for the ``default-src 'none'; sandbox`` Content-Security-Policy the logo
route sends to contain it. The check is therefore one format list rather than
two layers of defence, and there is no ``_looks_like_svg`` content sniff needed
because there is no ambiguous XML case to disambiguate.
"""

from typing import Any

import magic

from ..utils.errors import ValidationError

MAX_AVATAR_BYTES = 1 * 1024 * 1024

PNG_MIME = "image/png"
JPEG_MIME = "image/jpeg"
WEBP_MIME = "image/webp"

RASTER_MIMES = {PNG_MIME, JPEG_MIME, WEBP_MIME}

EXTENSION_MIMES = {
    ".png": PNG_MIME,
    ".jpg": JPEG_MIME,
    ".jpeg": JPEG_MIME,
    ".webp": WEBP_MIME,
}

ACCEPTED_COPY = "Avatar must be a PNG, JPEG or WEBP image under 1MB"


def mimetype_for_avatar(filename: str) -> str:
    """Download-time content type.

    Ingestion sniffs the real type from the bytes; on the way out only the stored
    filename is available, so the extension decides what the browser is told it
    is being served. Both branches were accepted at upload, so this can only ever
    mislabel a file the candidate uploaded themselves.
    """
    lowered = (filename or "").lower()
    for extension, mime in EXTENSION_MIMES.items():
        if lowered.endswith(extension):
            return mime
    return PNG_MIME


def validate_avatar(file_storage: Any) -> bytes:
    """Validate an avatar upload and return its raw bytes.

    Content type is sniffed from the bytes and never trusted from the filename.
    Raises a ``422`` ``ValidationError`` on oversize, empty, or wrong type.
    """
    avatar_bytes = file_storage.read()

    if len(avatar_bytes) > MAX_AVATAR_BYTES:
        raise ValidationError(
            "Avatar must be under 1MB",
            code="avatar_too_large",
            details=[{"field": "avatar", "message": ACCEPTED_COPY}],
        )

    if not avatar_bytes:
        raise ValidationError(
            "Avatar file is empty",
            code="avatar_invalid_type",
            details=[{"field": "avatar", "message": ACCEPTED_COPY}],
        )

    detected = magic.from_buffer(avatar_bytes, mime=True)
    if detected in RASTER_MIMES:
        return avatar_bytes

    raise ValidationError(
        "Avatar must be a PNG, JPEG or WEBP image",
        code="avatar_invalid_type",
        details=[{"field": "avatar", "message": ACCEPTED_COPY}],
    )
