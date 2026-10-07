"""Validation for employer company-logo uploads.

Kept separate from :mod:`app.services.cv_service` because the accepted formats,
the size ceiling and the failure codes are all different, and a logo has no
extraction step — it is stored and served, never parsed into text.

SVG is accepted because real company logos are frequently SVG. That is safe here
only because a logo is ever rendered through an ``<img>`` tag, in which context
browsers do not execute script; the serving route additionally sends a
``default-src 'none'; sandbox`` Content-Security-Policy so that navigating
directly to the logo URL cannot run script in the app's origin either.
"""

from typing import Any

import magic

from ..utils.errors import ValidationError

MAX_LOGO_BYTES = 1 * 1024 * 1024

PNG_MIME = "image/png"
JPEG_MIME = "image/jpeg"
WEBP_MIME = "image/webp"
SVG_MIME = "image/svg+xml"

RASTER_MIMES = {PNG_MIME, JPEG_MIME, WEBP_MIME}

# libmagic is inconsistent about SVG: with an XML prolog it reports image/svg+xml
# or text/xml, without one text/plain. Every one of those is only a *maybe*, so
# SVG additionally has to literally look like one (see ``_looks_like_svg``).
SVG_MIMES = {SVG_MIME, "text/xml", "text/plain", "image/svg"}

EXTENSION_MIMES = {
    ".png": PNG_MIME,
    ".jpg": JPEG_MIME,
    ".jpeg": JPEG_MIME,
    ".webp": WEBP_MIME,
    ".svg": SVG_MIME,
}

ACCEPTED_COPY = "Logo must be a PNG, JPEG, SVG or WEBP image under 1MB"


def mimetype_for_logo(filename: str) -> str:
    """Download-time content type.

    Ingestion sniffs the real type from the bytes; on the way out only the
    stored filename is available, so the extension decides what the browser is
    told it is being served. Both branches were accepted at upload, so this can
    only ever mislabel a file the employer uploaded themselves.
    """
    lowered = (filename or "").lower()
    for extension, mime in EXTENSION_MIMES.items():
        if lowered.endswith(extension):
            return mime
    return PNG_MIME


def validate_logo(file_storage: Any) -> bytes:
    """Validate a company-logo upload and return its raw bytes.

    Content type is sniffed from the bytes and never trusted from the filename.
    Raises a ``422`` ``ValidationError`` on oversize, empty, or wrong type.
    """
    logo_bytes = file_storage.read()

    if len(logo_bytes) > MAX_LOGO_BYTES:
        raise ValidationError(
            "Logo must be under 1MB",
            code="logo_too_large",
            details=[{"field": "logo", "message": ACCEPTED_COPY}],
        )

    if not logo_bytes:
        raise ValidationError(
            "Logo file is empty",
            code="logo_invalid_type",
            details=[{"field": "logo", "message": ACCEPTED_COPY}],
        )

    detected = magic.from_buffer(logo_bytes, mime=True)
    if detected in RASTER_MIMES:
        return logo_bytes
    if detected in SVG_MIMES and _looks_like_svg(logo_bytes):
        return logo_bytes

    raise ValidationError(
        "Logo must be a PNG, JPEG, SVG or WEBP image",
        code="logo_invalid_type",
        details=[{"field": "logo", "message": ACCEPTED_COPY}],
    )


def _looks_like_svg(logo_bytes: bytes) -> bool:
    """True when the leading bytes contain an ``<svg`` element.

    Guards the four ambiguous libmagic verdicts above. Any XML prolog, doctype
    or comment is skipped, so a well-formed SVG still passes while a plain-text
    file that libmagic happened to call ``text/plain`` does not.
    """
    head = logo_bytes[:1024].lstrip()
    lowered = head.lower()
    if lowered.startswith(b"<?xml"):
        lowered = lowered[lowered.find(b"?>") + 2 :].lstrip() if b"?>" in lowered else b""
    return b"<svg" in lowered
