"""ICP versions: company profile + ideal customer profile (CONTRACTS section 3, P0-2 + P1-3).

Every generation or edit is a new version; exactly one version per tenant is active (enforced by a partial
unique index). Written through app.services.icp_service.
"""

from typing import Any

from sqlalchemy import Boolean, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import enum_check

ICP_SOURCES = ("agent", "user")


class IcpVersion(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "icp_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="uq_icp_versions_tenant_id_version"),
        enum_check("source", ICP_SOURCES),
        Index(
            "uq_icp_versions_one_active",
            "tenant_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False)
    company_profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # CompanyProfile
    icp: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # ICP
    source: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
