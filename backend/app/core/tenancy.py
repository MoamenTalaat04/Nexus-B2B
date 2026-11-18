"""Tenant helpers (CONTRACTS section 5).

Stand-in written in P1-3 (the ICP builder needs the settings). P0-2 owns this file and adds `scoped(...)`.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenants import BusinessSettings


async def get_settings_for(session: AsyncSession, tenant_id: uuid.UUID) -> BusinessSettings:
    """The tenant's business settings; creates the default row if it is missing (flushed, not committed)."""
    row = (
        await session.execute(select(BusinessSettings).where(BusinessSettings.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if row is None:
        row = BusinessSettings(tenant_id=tenant_id)
        session.add(row)
        await session.flush()
        await session.refresh(row)  # load the server defaults
    return row
