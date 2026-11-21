"""Lead tables (CONTRACTS section 3).

Stand-in written in P2-1/P3-3 before P0-2 landed: search_queries, leads, contacts and lead_status_history,
column by column from the contract. P0-2 owns this file and added lead_notes and lead_outcomes
(migration 0006).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.refcodes import new_ref_code
from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import ContactType, LeadStatus, enum_check

CONTACT_SOURCES = ("google_places", "website", "manual", "lead_initiated")
ACTORS = ("agent", "user", "system")
OUTCOMES = ("won", "lost")


class SearchQuery(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "search_queries"
    __table_args__ = (Index("ix_search_queries_tenant_id_created_at", "tenant_id", "created_at"),)

    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # RegionTarget / RegionFilter
    results_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)


class Lead(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dedupe_key", name="uq_leads_tenant_id_dedupe_key"),
        UniqueConstraint("tenant_id", "ref_code", name="uq_leads_tenant_id_ref_code"),
        enum_check("status", LeadStatus),
        Index("ix_leads_tenant_id_status", "tenant_id", "status"),
        Index("ix_leads_tenant_id_next_action_at", "tenant_id", "next_action_at"),
    )

    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="manual")
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)  # e.g. the Google place_id
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    governorate: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_maps_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviews_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=LeadStatus.NEW.value)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_reasons: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    disqualify_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    icp_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sourcing_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sequence_step: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_paused: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    first_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ref_code: Mapped[str] = mapped_column(Text, nullable=False, default=new_ref_code)
    dedupe_key: Mapped[str | None] = mapped_column(Text, nullable=True)


class Contact(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "lead_id", "type", "value", name="uq_contacts_tenant_lead_type_value"),
        enum_check("type", ContactType),
        enum_check("source", CONTACT_SOURCES),
        Index("ix_contacts_lead_id", "lead_id"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)  # normalized (phones in E.164)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.5", default=0.5)


class LeadStatusHistory(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "lead_status_history"
    __table_args__ = (
        enum_check("actor", ACTORS),
        Index("ix_lead_status_history_lead_id", "lead_id"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class LeadNote(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "lead_notes"
    __table_args__ = (Index("ix_lead_notes_lead_id", "lead_id"),)

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)


class LeadOutcome(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    """Won/lost result set by the owner; the input of the feedback loop (P4-4)."""

    __tablename__ = "lead_outcomes"
    __table_args__ = (
        enum_check("outcome", OUTCOMES),
        Index("ix_lead_outcomes_lead_id", "lead_id"),
        Index("ix_lead_outcomes_tenant_id_created_at", "tenant_id", "created_at"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    value_egp: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
