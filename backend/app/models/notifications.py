"""Notifications (CONTRACTS section 3).

Stand-in written in P3-3 (the outreach tick notifies the owner about a missing template). P0-2 owns this file
and added learned_insights (migration 0006).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
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


class LearnedInsight(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    """One version of the feedback loop's output (P4-4). Exactly one active version per tenant (or none)."""

    __tablename__ = "learned_insights"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="uq_learned_insights_tenant_id_version"),
        Index("uq_learned_insights_one_active", "tenant_id", unique=True, postgresql_where=text("is_active")),
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False)
    insights: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
