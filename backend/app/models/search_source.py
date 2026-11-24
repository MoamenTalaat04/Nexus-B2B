"""Platform-level Search Source configurations managed by Super Admin."""

import uuid

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SearchSourceConfig(Base, TimestampMixin):
    __tablename__ = "search_source_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="custom")
    base_url: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extra_config: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
