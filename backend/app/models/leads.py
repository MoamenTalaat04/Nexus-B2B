"""Lead tables (CONTRACTS section 3).

Stand-in written in P2-1 with only `search_queries` (the query generator avoids repeating recent queries).
P0-2 owns this file and adds leads, contacts, lead_status_history, lead_notes and lead_outcomes here.
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPkMixin


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
