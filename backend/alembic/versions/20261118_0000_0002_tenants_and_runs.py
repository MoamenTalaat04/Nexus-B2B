"""tenants, agent_runs, agent_steps (P0-3: the tables tracing needs).

P0-2 adds the remaining tables in the next migration (revises 0002).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RUN_KINDS = "'icp_build', 'sourcing', 'scoring', 'enrichment', 'outreach_tick', 'reply', 'feedback'"
_RUN_STATUSES = "'queued', 'running', 'succeeded', 'failed', 'cancelled'"
_TRIGGERS = "'manual', 'schedule', 'webhook', 'chained'"
_STEP_TYPES = "'llm_call', 'tool_call', 'external_api', 'decision', 'error'"


def _base_columns() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "tenants",
        *_base_columns(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
    )

    op.create_table(
        "agent_runs",
        *_base_columns(),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE", name="fk_agent_runs_tenant_id_tenants"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("input", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("output_summary", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(12, 6), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_agent_runs"),
        sa.CheckConstraint(f"kind IN ({_RUN_KINDS})", name="ck_agent_runs_kind_valid"),
        sa.CheckConstraint(f"status IN ({_RUN_STATUSES})", name="ck_agent_runs_status_valid"),
        sa.CheckConstraint(f"trigger IN ({_TRIGGERS})", name="ck_agent_runs_trigger_valid"),
    )
    op.create_index("ix_agent_runs_tenant_id", "agent_runs", ["tenant_id"])
    op.create_index("ix_agent_runs_tenant_id_created_at", "agent_runs", ["tenant_id", "created_at"])

    op.create_table(
        "agent_steps",
        *_base_columns(),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE", name="fk_agent_steps_tenant_id_tenants"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="CASCADE", name="fk_agent_steps_run_id_agent_runs"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("input", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_agent_steps"),
        sa.CheckConstraint(f"step_type IN ({_STEP_TYPES})", name="ck_agent_steps_step_type_valid"),
    )
    op.create_index("ix_agent_steps_tenant_id", "agent_steps", ["tenant_id"])
    op.create_index("ix_agent_steps_run_id_seq", "agent_steps", ["run_id", "seq"])


def downgrade() -> None:
    op.drop_table("agent_steps")
    op.drop_table("agent_runs")
    op.drop_table("tenants")
