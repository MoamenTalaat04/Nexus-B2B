"""users, lead_notes, lead_outcomes, demo_routes, learned_insights (P0-2, CONTRACTS section 3).

The rest of the schema (0002-0005) was written by C as contract-exact stand-ins; this migration adds the
tables that were still missing. Written by hand from the models (same naming convention as autogenerate).
`updated_at` is maintained by the ORM (`onupdate=func.now()` in TimestampMixin), like every other table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-20 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
    ]


def _tenant_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id"], ["tenants.id"], name=op.f(f"fk_{table}_tenant_id_tenants"), ondelete="CASCADE"
    )


def upgrade() -> None:
    # users ------------------------------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), server_default="", nullable=False),
        sa.Column("role", sa.Text(), server_default="owner", nullable=False),
        *_base_columns(),
        sa.CheckConstraint("role IN ('owner', 'member')", name=op.f("ck_users_role_valid")),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
        _tenant_fk("users"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_tenant_id"), "users", ["tenant_id"], unique=False)

    # lead_notes -------------------------------------------------------------------------------------
    op.create_table(
        "lead_notes",
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("author_user_id", sa.UUID(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        *_base_columns(),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name=op.f("fk_lead_notes_lead_id_leads"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["users.id"],
            name=op.f("fk_lead_notes_author_user_id_users"),
            ondelete="SET NULL",
        ),
        _tenant_fk("lead_notes"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_notes")),
    )
    op.create_index(op.f("ix_lead_notes_tenant_id"), "lead_notes", ["tenant_id"], unique=False)
    op.create_index("ix_lead_notes_lead_id", "lead_notes", ["lead_id"], unique=False)

    # lead_outcomes ----------------------------------------------------------------------------------
    op.create_table(
        "lead_outcomes",
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("value_egp", sa.Numeric(14, 2), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        *_base_columns(),
        sa.CheckConstraint("outcome IN ('won', 'lost')", name=op.f("ck_lead_outcomes_outcome_valid")),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name=op.f("fk_lead_outcomes_lead_id_leads"), ondelete="CASCADE"
        ),
        _tenant_fk("lead_outcomes"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_outcomes")),
    )
    op.create_index(op.f("ix_lead_outcomes_tenant_id"), "lead_outcomes", ["tenant_id"], unique=False)
    op.create_index("ix_lead_outcomes_lead_id", "lead_outcomes", ["lead_id"], unique=False)
    op.create_index(
        "ix_lead_outcomes_tenant_id_created_at", "lead_outcomes", ["tenant_id", "created_at"], unique=False
    )

    # demo_routes ------------------------------------------------------------------------------------
    op.create_table(
        "demo_routes",
        sa.Column("test_phone", sa.Text(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        *_base_columns(),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name=op.f("fk_demo_routes_lead_id_leads"), ondelete="CASCADE"
        ),
        _tenant_fk("demo_routes"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_demo_routes")),
        sa.UniqueConstraint("tenant_id", "test_phone", name="uq_demo_routes_tenant_id_test_phone"),
    )
    op.create_index(op.f("ix_demo_routes_tenant_id"), "demo_routes", ["tenant_id"], unique=False)

    # learned_insights -------------------------------------------------------------------------------
    op.create_table(
        "learned_insights",
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "insights", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "stats", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_base_columns(),
        _tenant_fk("learned_insights"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learned_insights")),
        sa.UniqueConstraint("tenant_id", "version", name="uq_learned_insights_tenant_id_version"),
    )
    op.create_index(op.f("ix_learned_insights_tenant_id"), "learned_insights", ["tenant_id"], unique=False)
    op.create_index(
        "uq_learned_insights_one_active",
        "learned_insights",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("uq_learned_insights_one_active", table_name="learned_insights")
    op.drop_index(op.f("ix_learned_insights_tenant_id"), table_name="learned_insights")
    op.drop_table("learned_insights")
    op.drop_index(op.f("ix_demo_routes_tenant_id"), table_name="demo_routes")
    op.drop_table("demo_routes")
    op.drop_index("ix_lead_outcomes_tenant_id_created_at", table_name="lead_outcomes")
    op.drop_index("ix_lead_outcomes_lead_id", table_name="lead_outcomes")
    op.drop_index(op.f("ix_lead_outcomes_tenant_id"), table_name="lead_outcomes")
    op.drop_table("lead_outcomes")
    op.drop_index("ix_lead_notes_lead_id", table_name="lead_notes")
    op.drop_index(op.f("ix_lead_notes_tenant_id"), table_name="lead_notes")
    op.drop_table("lead_notes")
    op.drop_index(op.f("ix_users_tenant_id"), table_name="users")
    op.drop_table("users")
