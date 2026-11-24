"""Pydantic schemas for Super Admin LLM provider management."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ProviderType = Literal["groq", "openai", "gemini", "colab_vllm", "custom"]


class LlmProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider_type: ProviderType = "custom"
    base_url: str = Field(min_length=4, max_length=400)
    api_key: str = Field(min_length=1, max_length=500)
    model_smart: str = Field(min_length=1, max_length=200)
    model_fast: str = Field(default="", max_length=200)
    reasoning_models: str = Field(default="", max_length=400)
    priority: int = Field(default=1, ge=1, le=100)
    is_active: bool = True
    is_primary: bool = False


class LlmProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    provider_type: ProviderType | None = None
    base_url: str | None = Field(default=None, min_length=4, max_length=400)
    api_key: str | None = Field(default=None, min_length=1, max_length=500)
    model_smart: str | None = Field(default=None, min_length=1, max_length=200)
    model_fast: str | None = Field(default=None, min_length=1, max_length=200)
    reasoning_models: str | None = Field(default=None, max_length=400)
    priority: int | None = Field(default=None, ge=1, le=100)
    is_active: bool | None = None
    is_primary: bool | None = None


class LlmProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    provider_type: str
    base_url: str
    api_key_masked: str
    model_smart: str
    model_fast: str
    reasoning_models: str
    priority: int
    is_active: bool
    is_primary: bool
    created_at: datetime
    updated_at: datetime


class LlmProviderListOut(BaseModel):
    items: list[LlmProviderOut]
    total: int
    env_fallback_model_smart: str
    env_fallback_base_url: str


class LlmProviderTestOut(BaseModel):
    ok: bool
    status_code: int | None = None
    latency_ms: int
    models_count: int = 0
    model_checked: str | None = None
    reply_preview: str | None = None
    error: str | None = None


class LlmProviderReorderIn(BaseModel):
    ordered_ids: list[uuid.UUID]
