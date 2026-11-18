"""ICP versions (CONTRACTS section 9, P1-3).

Every generation (source="agent") or owner edit (source="user") is saved as a new version; exactly one
version per tenant is active. Functions flush but never commit: the caller owns the transaction.
"""

import uuid
from typing import Literal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.icp import IcpVersion
from app.models.tenants import Tenant
from app.schemas.agent_io import ICP, CompanyProfile

IcpSource = Literal["agent", "user"]


async def get_active_icp(session: AsyncSession, tenant_id: uuid.UUID) -> IcpVersion | None:
    return (
        await session.execute(
            select(IcpVersion).where(IcpVersion.tenant_id == tenant_id, IcpVersion.is_active.is_(True))
        )
    ).scalar_one_or_none()


async def list_versions(session: AsyncSession, tenant_id: uuid.UUID) -> list[IcpVersion]:
    """All versions, newest first."""
    rows = await session.execute(
        select(IcpVersion).where(IcpVersion.tenant_id == tenant_id).order_by(IcpVersion.version.desc())
    )
    return list(rows.scalars())


async def save_version(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    profile: CompanyProfile,
    icp: ICP,
    source: IcpSource,
    notes: str | None = None,
) -> int:
    """Save a new active version, deactivate the others (caller's transaction). Returns its number."""
    # Lock the tenant row so two saves at the same time cannot pick the same version number.
    await session.execute(select(Tenant.id).where(Tenant.id == tenant_id).with_for_update())
    current = await session.scalar(
        select(func.coalesce(func.max(IcpVersion.version), 0)).where(IcpVersion.tenant_id == tenant_id)
    )
    version = int(current or 0) + 1
    await session.execute(
        update(IcpVersion)
        .where(IcpVersion.tenant_id == tenant_id, IcpVersion.is_active.is_(True))
        .values(is_active=False)
    )
    session.add(
        IcpVersion(
            tenant_id=tenant_id,
            version=version,
            company_profile=profile.model_dump(mode="json"),
            icp=icp.model_dump(mode="json"),
            source=source,
            is_active=True,
            notes=notes,
        )
    )
    await session.flush()
    return version
