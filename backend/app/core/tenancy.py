"""Tenant helpers (CONTRACTS section 5).

Stand-in written in P1-3 (the ICP builder needs the settings). P0-2 owns this file and added `scoped(...)`.
"""

import uuid
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenants import BusinessSettings


def scoped[S: Select[Any]](stmt: S, model: Any, tenant_id: uuid.UUID) -> S:
    """Add `WHERE model.tenant_id = :tenant_id` to a select. The tenant id must come from the authenticated
    user or the job's arguments, never from the request body.

        rows = await session.execute(scoped(select(Lead).where(Lead.status == "new"), Lead, user.tenant_id))
    """
    column = getattr(model, "tenant_id", None)
    if column is None:
        raise TypeError(f"{getattr(model, '__name__', model)!r} is not tenant-scoped (no tenant_id column).")
    return stmt.where(column == tenant_id)


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
