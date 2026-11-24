"""Pydantic schemas for Knowledge upload/list APIs (P1-1)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime_type: str
    size_bytes: int
    char_count: int
    status: str
    error: str | None = None
    preview: str | None = None
    created_at: datetime


class KnowledgeFileListOut(BaseModel):
    items: list[KnowledgeFileOut] = Field(default_factory=list)
    total: int = 0


class KnowledgeFileDetailOut(KnowledgeFileOut):
    content: str = ""
    editable: bool = False


class KnowledgeFileUpdateIn(BaseModel):
    content: str = Field(max_length=200_000)
