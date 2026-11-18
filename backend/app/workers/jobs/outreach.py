"""job_outreach_tick (CONTRACTS section 10, P3-3): every 5 minutes, one outreach pass per enabled tenant."""

import logging
from datetime import UTC, datetime
from typing import Any

from arq.cron import cron
from sqlalchemy import select

from app.db import SessionLocal
from app.models.tenants import BusinessSettings
from app.services import outreach

logger = logging.getLogger("app.jobs.outreach")


async def job_outreach_tick(ctx: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        tenant_ids = list(
            (
                await session.execute(
                    select(BusinessSettings.tenant_id).where(BusinessSettings.agent_enabled.is_(True))
                )
            ).scalars()
        )
    summary: dict[str, Any] = {"tenants": len(tenant_ids), "created": 0}
    for tenant_id in tenant_ids:
        try:
            async with SessionLocal() as session:
                settings = (
                    await session.execute(
                        select(BusinessSettings).where(BusinessSettings.tenant_id == tenant_id)
                    )
                ).scalar_one()
                result = await outreach.tick_tenant(session, settings, now=now)
                summary["created"] += result.created
        except Exception:  # one tenant's failure must not stop the others (already traced if inside a run)
            logger.exception("outreach tick failed for tenant %s", tenant_id)
    return summary


CRON_JOBS = [cron(job_outreach_tick, minute=set(range(0, 60, 5)), run_at_startup=False)]
