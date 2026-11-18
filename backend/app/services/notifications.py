"""Owner notifications (CONTRACTS section 9).

Minimal stand-in written in P3-3 (contract signature, inserts the row only). D owns this file: P3-4 writes the
minimal version and P4-2 adds Telegram.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import Notification


async def notify_owner(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    kind: str,
    title: str,
    body: str,
    lead_id: uuid.UUID | None = None,
) -> None:
    session.add(Notification(tenant_id=tenant_id, kind=kind, title=title, body=body, lead_id=lead_id))
    await session.flush()
