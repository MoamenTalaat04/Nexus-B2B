"""Platform-level LLM provider configurations managed by Super Admin."""

import uuid

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LlmProviderConfig(Base, TimestampMixin):
    __tablename__ = "llm_provider_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False, default="custom")
    base_url: Mapped[str] = mapped_column(String(400), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    model_smart: Mapped[str] = mapped_column(String(200), nullable=False)
    model_fast: Mapped[str] = mapped_column(String(200), nullable=False)
    reasoning_models: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
