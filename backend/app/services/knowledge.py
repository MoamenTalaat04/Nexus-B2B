"""Knowledge-file extraction and search services (P1-1)."""

import logging
import re
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("app.services.knowledge")

MAX_PREVIEW_CHARS = 300
SCANNED_PDF_CHAR_THRESHOLD = 20
MAX_OMISSION_NOTE_CHARS = 1_000


class KnowledgeExtractionError(Exception):
    """Safe extraction failure used by the Knowledge API."""


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"[^\S\r\n]+", " ", text.replace("\r\n", "\n").replace("\r", "\n")).strip()


def extract_knowledge_text(path: str | Path, mime_type: str) -> str:
    """Extract normalized text from an already size-validated local file."""
    file_path = Path(path)
    normalized_mime = mime_type.lower().strip()

    try:
        if normalized_mime == "application/pdf" or file_path.suffix.lower() == ".pdf":
            reader = PdfReader(str(file_path))
            text = "\n\n".join(str(page.extract_text() or "") for page in reader.pages)
        elif (
            normalized_mime
            in {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/docx",
            }
            or file_path.suffix.lower() == ".docx"
        ):
            from docx import Document

            document = Document(str(file_path))
            text = "\n".join(str(paragraph.text) for paragraph in document.paragraphs)
        elif normalized_mime in {"text/markdown", "text/plain"} or file_path.suffix.lower() in {
            ".md",
            ".txt",
        }:
            text = file_path.read_text(encoding="utf-8")
        else:
            raise KnowledgeExtractionError("unsupported_file_type")
    except KnowledgeExtractionError:
        raise
    except Exception as exc:
        logger.exception("Knowledge text extraction failed")
        raise KnowledgeExtractionError("extraction_failed") from exc

    return _normalize_whitespace(text)


def is_scanned_pdf(text: str) -> bool:
    return len(text.strip()) < SCANNED_PDF_CHAR_THRESHOLD


def preview_text(text: str | None) -> str:
    if not text:
        return ""
    return text[:MAX_PREVIEW_CHARS]


def _knowledge_model() -> type[Any]:
    from app.models.knowledge import KnowledgeFile

    return KnowledgeFile


@dataclass(frozen=True)
class _KnowledgeBlock:
    filename: str
    text: str

    @property
    def rendered(self) -> str:
        return f"### {self.filename}\n{self.text}"


def _bounded_omission_note(filenames: list[str]) -> str | None:
    if not filenames:
        return None
    note = "\n\n[Omitted files: " + ", ".join(sorted(set(filenames))) + "]"
    if len(note) > MAX_OMISSION_NOTE_CHARS:
        return None
    return note


def _build_knowledge_text(blocks: list[_KnowledgeBlock], max_chars: int) -> str:
    if max_chars <= 0:
        return ""

    complete_blocks = [block for block in blocks if block.filename.strip() and block.text.strip()]

    all_blocks = "\n\n".join(block.rendered for block in complete_blocks)
    if len(all_blocks) <= max_chars:
        return all_blocks

    for prefix_size in range(len(complete_blocks) - 1, 0, -1):
        selected = complete_blocks[:prefix_size]
        omitted = complete_blocks[prefix_size:]
        base = "\n\n".join(block.rendered for block in selected)
        omission_note = _bounded_omission_note([block.filename for block in omitted])
        if omission_note is not None and len(base) + len(omission_note) <= max_chars:
            return base + omission_note

    for prefix_size in range(len(complete_blocks), 0, -1):
        base = "\n\n".join(block.rendered for block in complete_blocks[:prefix_size])
        if len(base) <= max_chars:
            return base

    return ""


async def get_knowledge_text(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    max_chars: int = 120_000,
) -> str:
    """Concatenate complete ready KnowledgeFile blocks for one tenant."""
    knowledge_model = _knowledge_model()
    rows = (
        (
            await session.execute(
                select(knowledge_model)
                .where(
                    knowledge_model.tenant_id == tenant_id,
                    knowledge_model.status == "ready",
                )
                .order_by(knowledge_model.created_at.asc(), knowledge_model.id.asc())
            )
        )
        .scalars()
        .all()
    )

    blocks = [
        _KnowledgeBlock(filename=str(row.filename), text=str(row.extracted_text or ""))
        for row in rows
        if str(row.extracted_text or "").strip()
    ]
    return _build_knowledge_text(blocks, max_chars)


ARABIC_DIACRITIC_RANGE = "\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed"
_ARABIC_DIACRITICS = re.compile(f"[{ARABIC_DIACRITIC_RANGE}]")


def normalize_search_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _ARABIC_DIACRITICS.sub("", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه").replace("ى", "ي")
    return " ".join(text.lower().split())


def _split_paragraphs(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        remaining = len(text) - start
        if remaining <= 800:
            chunks.append(text[start:])
            break

        window = text[start : start + 800]
        boundary = window.rfind(" ")
        newline_boundary = window.rfind("\n")
        if newline_boundary >= 300:
            boundary = newline_boundary
        elif boundary < 300:
            boundary = 799

        end = start + boundary + 1
        chunks.append(text[start:end])
        start = end
    return chunks


async def search_knowledge(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    query: str,
    k: int = 5,
) -> list[str]:
    """Return the top tenant-scoped keyword matches prefixed with their filename."""
    if k <= 0:
        return []

    knowledge_model = _knowledge_model()
    rows = (
        (
            await session.execute(
                select(knowledge_model)
                .where(
                    knowledge_model.tenant_id == tenant_id,
                    knowledge_model.status == "ready",
                )
                .order_by(knowledge_model.created_at.asc(), knowledge_model.id.asc())
            )
        )
        .scalars()
        .all()
    )

    query_words = set(normalize_search_text(query).split())
    if not query_words:
        return []

    matches: list[tuple[int, str, str, str]] = []
    for row in rows:
        text = str(row.extracted_text or "")
        filename = str(row.filename)
        for paragraph in _split_paragraphs(text):
            words = set(normalize_search_text(paragraph).split())
            overlap = len(query_words & words)
            if overlap:
                matches.append((overlap, filename, str(row.id), f"{filename}: {paragraph}"))

    matches.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
    return [item[3] for item in matches[:k]]
