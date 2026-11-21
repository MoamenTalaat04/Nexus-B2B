"""Knowledge files (CONTRACTS section 3, owners P0-2 / P1-1; migration 0007).

One uploaded company file per row. The API (app/api/knowledge.py) saves the file under UPLOAD_DIR, extracts
its text synchronously and sets status; services/knowledge.py reads the `ready` rows for the ICP builder.
"""

from sqlalchemy import BigInteger, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import enum_check

KNOWLEDGE_FILE_STATUSES = ("processing", "ready", "failed")


class KnowledgeFile(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "knowledge_files"
    __table_args__ = (
        enum_check("status", KNOWLEDGE_FILE_STATUSES),
        Index("ix_knowledge_files_tenant_id_created_at", "tenant_id", "created_at"),
    )

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="processing", default="processing"
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
