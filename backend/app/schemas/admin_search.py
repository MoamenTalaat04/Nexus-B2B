"""Pydantic schemas for Super Admin Search Sources management."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SearchSourceType = Literal[
    "openstreetmap",
    "google_places",
    "google_search",
    "linkedin",
    "facebook",
    "instagram",
    "x_twitter",
    "reddit",
    "custom",
]


class SearchSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source_type: SearchSourceType = "custom"
    base_url: str = Field(default="", max_length=400)
    api_key: str = Field(default="", max_length=500)
    extra_config: str = Field(default="", max_length=400)
    priority: int = Field(default=1, ge=1, le=100)
    is_active: bool = True
    is_primary: bool = False


class SearchSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    source_type: SearchSourceType | None = None
    base_url: str | None = Field(default=None, max_length=400)
    api_key: str | None = Field(default=None, max_length=500)
    extra_config: str | None = Field(default=None, max_length=400)
    priority: int | None = Field(default=None, ge=1, le=100)
    is_active: bool | None = None
    is_primary: bool | None = None


class SearchSourceOut(BaseModel):
    id: uuid.UUID
    name: str
    source_type: str
    base_url: str
    api_key_masked: str
    has_api_key: bool
    extra_config: str
    priority: int
    is_active: bool
    is_primary: bool
    created_at: datetime
    updated_at: datetime


class SearchSourceListOut(BaseModel):
    items: list[SearchSourceOut]
    total: int


class SearchSourceTestOut(BaseModel):
    ok: bool
    status_code: int | None = None
    latency_ms: int
    sample_count: int = 0
    error: str | None = None


class SearchSourceReorderIn(BaseModel):
    ordered_ids: list[uuid.UUID]
