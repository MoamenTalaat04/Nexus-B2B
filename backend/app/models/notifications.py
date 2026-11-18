"""Notifications (CONTRACTS section 3).

Stand-in written in P3-3 (the outreach tick notifies the owner about a missing template). P0-2 owns this file
and adds learned_insights here.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import enum_check

NOTIFICATION_KINDS = (
    "hot_lead",
    "wants_management",
    "wants_offer",
    "needs_approval",
    "channel_error",
    "run_failed",
)


class Notification(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        enum_check("kind", NOTIFICATION_KINDS),
        Index("ix_notifications_tenant_id_created_at", "tenant_id", "created_at"),
    )

    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    telegram_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
