"""Agent runs and their steps: the trace of everything an agent did (CONTRACTS section 3, owners P0-2 + P0-3).

Written by app.core.tracing; read by GET /api/v1/runs (Agent Activity) and the reports.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import AgentRunKind, AgentRunStatus, StepType, enum_check

RUN_TRIGGERS = ("manual", "schedule", "webhook", "chained")


class AgentRun(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        enum_check("kind", AgentRunKind),
        enum_check("status", AgentRunStatus),
        enum_check("trigger", RUN_TRIGGERS),
        Index("ix_agent_runs_tenant_id_created_at", "tenant_id", "created_at"),
    )

    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=AgentRunStatus.QUEUED.value)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    output_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    total_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, server_default="0", default=Decimal(0)
    )


class AgentStep(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        enum_check("step_type", StepType),
        Index("ix_agent_steps_run_id_seq", "run_id", "seq"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    input: Mapped[Any] = mapped_column(JSONB, nullable=True)
    output: Mapped[Any] = mapped_column(JSONB, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, server_default="0", default=Decimal(0)
    )
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    # No FK yet: the leads table arrives in P0-2, which can add the constraint.
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
