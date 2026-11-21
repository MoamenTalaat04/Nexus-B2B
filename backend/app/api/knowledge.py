"""Knowledge-file upload, listing and deletion API (P1-1)."""

import asyncio
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import AppError
from app.core.security import CurrentUser, get_current_user
from app.db import get_session
from app.schemas.knowledge import KnowledgeFileListOut, KnowledgeFileOut
from app.services.knowledge import (
    KnowledgeExtractionError,
    extract_knowledge_text,
    is_scanned_pdf,
    preview_text,
)

logger = logging.getLogger("app.api.knowledge")

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TENANT_FILES = 20
READ_CHUNK_BYTES = 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt", ".docx"}


def _knowledge_model() -> type[Any]:
    from app.models.knowledge import KnowledgeFile

    return KnowledgeFile


def _safe_filename(filename: str) -> str:
    safe = Path(filename).name
    safe = "".join(ch for ch in safe if ch not in {"/", "\\", "\x00", "\r", "\n"})
    safe = safe.strip()
    if not safe:
        raise AppError("missing_file", "The uploaded file needs a filename.", status_code=422)
    return safe


def _mime_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }[suffix]


async def _read_upload_to_temp(upload: UploadFile, tenant_id: uuid.UUID) -> tuple[Path, int]:
    temp_dir = Path(settings.UPLOAD_DIR) / ".tmp" / str(tenant_id)
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{uuid.uuid4()}.upload"
    size = 0

    try:
        with temp_path.open("xb") as target:
            while True:
                remaining = MAX_FILE_BYTES + 1 - size
                if remaining <= 0:
                    break
                chunk = await upload.read(min(READ_CHUNK_BYTES, remaining))
                if not chunk:
                    break
                target.write(chunk)
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    break
    except Exception as exc:
        await asyncio.to_thread(temp_path.unlink, missing_ok=True)
        logger.exception("Could not write Knowledge upload temporary file")
        raise AppError("storage_error", "The uploaded file could not be stored.", status_code=500) from exc

    if size > MAX_FILE_BYTES:
        await asyncio.to_thread(temp_path.unlink, missing_ok=True)
        raise AppError("file_too_large", "Each Knowledge file must be 10 MiB or smaller.", status_code=413)
    return temp_path, size


async def _count_tenant_files(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    knowledge_model = _knowledge_model()
    count = await session.scalar(
        select(func.count()).select_from(knowledge_model).where(knowledge_model.tenant_id == tenant_id)
    )
    return int(count or 0)


async def _list_tenant_files(session: AsyncSession, tenant_id: uuid.UUID) -> list[Any]:
    knowledge_model = _knowledge_model()
    rows = (
        (
            await session.execute(
                select(knowledge_model)
                .where(knowledge_model.tenant_id == tenant_id)
                .order_by(knowledge_model.created_at.desc(), knowledge_model.id.desc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def _find_tenant_file(session: AsyncSession, tenant_id: uuid.UUID, file_id: uuid.UUID) -> Any | None:
    knowledge_model = _knowledge_model()
    return (
        await session.execute(
            select(knowledge_model).where(
                knowledge_model.id == file_id,
                knowledge_model.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()


def _to_out(row: Any) -> KnowledgeFileOut:
    return KnowledgeFileOut.model_validate(
        {
            "id": row.id,
            "filename": row.filename,
            "mime_type": row.mime_type,
            "size_bytes": row.size_bytes,
            "char_count": row.char_count,
            "status": row.status,
            "error": row.error,
            "preview": preview_text(row.extracted_text),
            "created_at": row.created_at,
        }
    )


@router.post("", response_model=KnowledgeFileOut, status_code=201)
async def upload_knowledge(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> KnowledgeFileOut:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise AppError(
            "unsupported_file_type",
            "Only PDF, MD, TXT and DOCX files are supported.",
            status_code=415,
        )

    count = await _count_tenant_files(session, user.tenant_id)
    if count >= MAX_TENANT_FILES:
        raise AppError(
            "knowledge_file_limit_reached",
            "This tenant has reached the 20-file Knowledge limit.",
            status_code=409,
        )

    safe_filename = _safe_filename(filename)
    temp_path: Path | None = None
    final_path: Path | None = None
    row: Any | None = None

    try:
        temp_path, size = await _read_upload_to_temp(file, user.tenant_id)

        tenant_dir = Path(settings.UPLOAD_DIR) / str(user.tenant_id)
        tenant_dir.mkdir(parents=True, exist_ok=True)
        final_path = tenant_dir / f"{uuid.uuid4()}_{safe_filename}"
        shutil.move(str(temp_path), str(final_path))
        temp_path = None

        try:
            knowledge_model = _knowledge_model()
            row = knowledge_model(
                tenant_id=user.tenant_id,
                filename=safe_filename,
                mime_type=_mime_type(safe_filename),
                size_bytes=size,
                storage_path=str(final_path),
                extracted_text=None,
                char_count=0,
                status="processing",
                error=None,
            )
            session.add(row)
            await session.flush()
        except AppError:
            await asyncio.to_thread(final_path.unlink, missing_ok=True)
            raise
        except Exception as exc:
            await asyncio.to_thread(final_path.unlink, missing_ok=True)
            logger.exception("Knowledge model integration failed for tenant %s", user.tenant_id)
            raise AppError(
                "knowledge_integration_error",
                "Knowledge file processing is unavailable.",
                status_code=500,
            ) from exc

        try:
            text = extract_knowledge_text(final_path, row.mime_type)
        except KnowledgeExtractionError as exc:
            row.status = "failed"
            row.error = "extraction_failed"
            row.extracted_text = None
            row.char_count = 0
            logger.warning("Knowledge extraction failed for tenant %s: %s", user.tenant_id, exc)
        else:
            row.extracted_text = text
            row.char_count = len(text)
            if suffix == ".pdf" and is_scanned_pdf(text):
                row.status = "ready"
                row.error = "no_text_extracted_maybe_scanned"
            else:
                row.status = "ready"
                row.error = None

        try:
            await session.commit()
            await session.refresh(row)
        except Exception as exc:
            await session.rollback()
            if final_path is not None:
                await asyncio.to_thread(final_path.unlink, missing_ok=True)
            logger.exception("Could not persist Knowledge file for tenant %s", user.tenant_id)
            raise AppError(
                "storage_error",
                "The Knowledge file could not be saved.",
                status_code=500,
            ) from exc

        return _to_out(row)
    finally:
        if temp_path is not None:
            await asyncio.to_thread(temp_path.unlink, missing_ok=True)
        await file.close()


@router.get("", response_model=KnowledgeFileListOut)
async def list_knowledge(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> KnowledgeFileListOut:
    rows = await _list_tenant_files(session, user.tenant_id)
    return KnowledgeFileListOut(items=[_to_out(row) for row in rows], total=len(rows))


@router.delete("/{file_id}", status_code=204)
async def delete_knowledge(
    file_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await _find_tenant_file(session, user.tenant_id, file_id)
    if row is None:
        raise AppError("knowledge_file_not_found", "Knowledge file not found.", status_code=404)

    try:
        stored_path = Path(str(row.storage_path))
        await asyncio.to_thread(stored_path.unlink, missing_ok=True)
    except OSError as exc:
        logger.exception("Could not remove stored Knowledge file for tenant %s", user.tenant_id)
        raise AppError("storage_error", "The Knowledge file could not be removed.", status_code=500) from exc

    await session.delete(row)
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.exception("Could not delete Knowledge database row for tenant %s", user.tenant_id)
        raise AppError("storage_error", "The Knowledge file could not be removed.", status_code=500) from exc
