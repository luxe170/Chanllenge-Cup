"""Extract plain text from uploaded resume files (PDF / DOCX / TXT)."""
from __future__ import annotations

import io
import unicodedata
from typing import Final


SUPPORTED_EXTENSIONS: Final[tuple[str, ...]] = (".pdf", ".doc", ".docx", ".txt", ".md")


class ResumeTextError(ValueError):
    """Raised when a resume file cannot be parsed into text."""


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _read_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:  # pragma: no cover - dep is declared, guard for safety
        raise ResumeTextError("pypdf is required to parse PDF resumes") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # pypdf raises many subclasses; treat all as bad input
        raise ResumeTextError(f"invalid pdf file: {exc}") from exc
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - one bad page shouldn't fail the whole resume
            parts.append("")
    return "\n".join(parts)


def _read_docx(data: bytes) -> str:
    try:
        from docx import Document  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise ResumeTextError("python-docx is required to parse DOCX resumes") from exc
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise ResumeTextError(f"invalid docx file: {exc}") from exc
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def _read_plain(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ResumeTextError("resume text encoding not recognized")


def extract_resume_text(filename: str, data: bytes) -> str:
    """Return normalized text extracted from ``data``, dispatched by extension."""

    if not data:
        raise ResumeTextError("empty file")
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        text = _read_pdf(data)
    elif lower.endswith(".docx"):
        text = _read_docx(data)
    elif lower.endswith(".doc"):
        # Legacy binary .doc is not covered by python-docx. Ask for a converted file.
        raise ResumeTextError("legacy .doc files are not supported; please upload .docx or .pdf")
    elif lower.endswith((".txt", ".md")):
        text = _read_plain(data)
    else:
        raise ResumeTextError(f"unsupported resume format: {filename}")
    normalized = _normalize(text)
    if not normalized:
        raise ResumeTextError("could not extract any text from the resume")
    return normalized
