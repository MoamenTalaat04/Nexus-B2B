"""knowledge_files (P0-2 / P1-1, CONTRACTS section 3).

P1-1's API and service read this table, but it was missing from main. Written by hand from
app/models/knowledge.py (same naming convention as autogenerate).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-21 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_files",
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("char_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.Text(), server_default="processing", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "status IN ('processing', 'ready', 'failed')", name=op.f("ck_knowledge_files_status_valid")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_knowledge_files_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_files")),
    )
    op.create_index(op.f("ix_knowledge_files_tenant_id"), "knowledge_files", ["tenant_id"], unique=False)
    op.create_index(
        "ix_knowledge_files_tenant_id_created_at",
        "knowledge_files",
        ["tenant_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_files_tenant_id_created_at", table_name="knowledge_files")
    op.drop_index(op.f("ix_knowledge_files_tenant_id"), table_name="knowledge_files")
    op.drop_table("knowledge_files")
