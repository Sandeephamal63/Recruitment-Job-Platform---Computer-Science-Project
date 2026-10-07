"""Minimal single-page PDF writer for the demo seed.

The seed needs CVs that are *real* files, not a text file with a PDF extension:
``cv_service`` sniffs the actual bytes, extracts text with pdfminer, and streams
the original back to the browser on download. A seeded row that only existed in
the database would make the CV-download and CV-parse paths look broken in a
demo while the matching scores quietly came from somewhere else.

Writing the handful of PDF objects this needs by hand avoids pulling a PDF
generation library into the server image purely for a dev fixture. It handles
exactly what the seed needs — one page, Helvetica, wrapped plain text — and
raises rather than emitting a malformed file if asked for more.
"""

from textwrap import wrap

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN = 48
FONT_SIZE = 10
LINE_HEIGHT = 14
MAX_CHARS_PER_LINE = 92
LINES_PER_PAGE_FLOOR = (PAGE_HEIGHT - 2 * MARGIN) // LINE_HEIGHT


class PdfBuildError(ValueError):
    pass


def build_text_pdf(text: str, *, title: str = "Curriculum Vitae") -> bytes:
    """Render ``text`` as a single-page PDF and return the file bytes."""
    lines: list[str] = []
    if title:
        lines.append(title)
        lines.append("")
    lines.extend(_wrap(text))
    if len(lines) > LINES_PER_PAGE_FLOOR:
        raise PdfBuildError(
            f"seed CV text is too long for the one-page builder "
            f"({len(lines)} lines, limit {LINES_PER_PAGE_FLOOR})"
        )

    content = _content_stream(lines)
    objects = _objects(content)
    return _assemble(objects)


def _wrap(text: str) -> list[str]:
    lines: list[str] = []
    for paragraph in (text or "").splitlines():
        stripped = paragraph.strip()
        if not stripped:
            lines.append("")
            continue
        lines.extend(wrap(stripped, width=MAX_CHARS_PER_LINE) or [""])
    return lines


def _escape(value: str) -> str:
    return value.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _content_stream(lines: list[str]) -> bytes:
    parts = [f"BT /F1 {FONT_SIZE} Tf {LINE_HEIGHT} TL {MARGIN} {PAGE_HEIGHT - MARGIN} Td"]
    for line in lines:
        parts.append(f"({_escape(line)}) Tj T*")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1", errors="replace")


def _objects(content: bytes) -> list[bytes]:
    """The five objects a single-page document needs, in order."""
    return [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "
            f"{PAGE_WIDTH} {PAGE_HEIGHT}] /Contents 4 0 R /Resources "
            "<< /Font << /F1 5 0 R >> >> >>"
        ).encode("latin-1"),
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]


def _assemble(objects: list[bytes]) -> bytes:
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    return bytes(out)
