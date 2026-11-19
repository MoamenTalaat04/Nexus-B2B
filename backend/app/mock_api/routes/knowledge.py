"""Mock Knowledge management routes: /knowledge."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from app.core.errors import AppError, NotFoundError
from app.core.security import CurrentUser
from app.mock_api.helpers import get_mock_current_user
from app.mock_api.state import MockKnowledgeFile, get_store

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt", ".docx"}
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_FILES_PER_TENANT = 20


class KnowledgeItemOut(BaseModel):
    id: uuid.UUID
    filename: str
    mime_type: str
    size_bytes: int
    char_count: int
    status: str
    error: str | None
    preview: str
    created_at: datetime


class KnowledgeDetailOut(KnowledgeItemOut):
    extracted_text: str


class KnowledgeListOut(BaseModel):
    items: list[KnowledgeItemOut]
    total: int


def _to_item(k: MockKnowledgeFile) -> KnowledgeItemOut:
    return KnowledgeItemOut(
        id=k.id,
        filename=k.filename,
        mime_type=k.mime_type,
        size_bytes=k.size_bytes,
        char_count=k.char_count,
        status=k.status,
        error=k.error,
        preview=k.extracted_text[:300],
        created_at=k.created_at,
    )


@router.get("", response_model=KnowledgeListOut)
async def list_knowledge(current_user: CurrentUser = Depends(get_mock_current_user)) -> KnowledgeListOut:
    store = get_store()
    rows = [k for k in store.knowledge.values() if k.tenant_id == current_user.tenant_id]
    rows.sort(key=lambda x: x.created_at, reverse=True)
    return KnowledgeListOut(items=[_to_item(r) for r in rows], total=len(rows))


@router.post("", response_model=KnowledgeItemOut, status_code=201)
async def upload_knowledge(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> KnowledgeItemOut:
    store = get_store()
    existing = [k for k in store.knowledge.values() if k.tenant_id == current_user.tenant_id]
    if len(existing) >= MAX_FILES_PER_TENANT:
        raise AppError("too_many_files", "Maximum 20 knowledge files per tenant.", status_code=400)

    filename = file.filename or "document.txt"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError(
            "unsupported_file_type",
            f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            status_code=422,
        )

    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise AppError("file_too_large", "File exceeds 10 MB limit.", status_code=422)

    if ext in {".md", ".txt"}:
        extracted = content.decode("utf-8", errors="replace").strip() or f"Mock content for {filename}"
    else:
        extracted = (
            f"### {filename}\nملخص مستخرج تلقائياً (Mock) — منتجات الشركة، الأسعار، وشروط التوريد والتوصيل."
        )

    doc = MockKnowledgeFile(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        filename=filename,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        extracted_text=extracted,
        char_count=len(extracted),
        status="ready",
        created_at=datetime.now(UTC),
    )
    store.knowledge[doc.id] = doc
    return _to_item(doc)


@router.get("/{doc_id}", response_model=KnowledgeDetailOut)
async def get_knowledge_doc(
    doc_id: uuid.UUID, current_user: CurrentUser = Depends(get_mock_current_user)
) -> KnowledgeDetailOut:
    store = get_store()
    doc = store.knowledge.get(doc_id)
    if doc is None or doc.tenant_id != current_user.tenant_id:
        raise NotFoundError("knowledge_file")
    return KnowledgeDetailOut(**_to_item(doc).model_dump(), extracted_text=doc.extracted_text)


@router.delete("/{doc_id}", status_code=204)
async def delete_knowledge(
    doc_id: uuid.UUID, current_user: CurrentUser = Depends(get_mock_current_user)
) -> None:
    store = get_store()
    doc = store.knowledge.get(doc_id)
    if doc is None or doc.tenant_id != current_user.tenant_id:
        raise NotFoundError("knowledge_file")
    del store.knowledge[doc_id]
