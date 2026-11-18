"""Messaging tables (CONTRACTS section 3).

Stand-in written in P3-3 before P0-2 landed: channel_connections, message_templates, conversations and
messages, column by column from the contract. P0-2 owns this file and adds demo_routes here.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import (
    ChannelType,
    MessageAuthor,
    MessageDirection,
    MessageKind,
    MessageStatus,
    OutreachPurpose,
    ReplyIntent,
    enum_check,
)


class ChannelConnection(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "channel_connections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "channel", name="uq_channel_connections_tenant_id_channel"),
        enum_check("channel", ChannelType),
        enum_check("status", ("connected", "error", "disconnected")),
    )

    channel: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="disconnected")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)  # non-secret ids
    secrets_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet JSON
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class MessageTemplate(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "message_templates"
    __table_args__ = (
        enum_check("channel", ChannelType),
        enum_check("purpose", ("intro", "followup")),
        enum_check("status", ("approved", "pending", "rejected")),
    )

    channel: Mapped[str] = mapped_column(Text, nullable=False, server_default=ChannelType.WHATSAPP.value)
    name: Mapped[str] = mapped_column(Text, nullable=False)  # Meta template name
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default="ar")
    category: Mapped[str] = mapped_column(Text, nullable=False, server_default="MARKETING")
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)  # with {{1}}, {{2}} … placeholders
    param_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")


class Conversation(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "lead_id", "channel", name="uq_conversations_tenant_lead_channel"),
        enum_check("channel", ChannelType),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    contact_value: Mapped[str] = mapped_column(Text, nullable=False, server_default="")  # lead's E.164
    window_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Message(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        enum_check("direction", MessageDirection),
        enum_check("channel", ChannelType),
        enum_check("author", MessageAuthor),
        enum_check("kind", MessageKind),
        enum_check("purpose", OutreachPurpose),
        enum_check("status", MessageStatus),
        enum_check("reply_intent", ReplyIntent),
        Index("ix_messages_tenant_id_lead_id_created_at", "tenant_id", "lead_id", "created_at"),
        Index("ix_messages_tenant_id_status", "tenant_id", "status"),
    )

    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False, server_default=ChannelType.WHATSAPP.value)
    author: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_params: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(Text, nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reply_intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    redirected_to: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
