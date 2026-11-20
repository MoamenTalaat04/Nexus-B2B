"""job_daily_cycle (CONTRACTS section 10, P2-2): cron 09:00 Africa/Cairo.

For every tenant with agent_enabled and onboarding_completed whose working_days include today (Cairo), enqueue
job_run_sourcing(tenant_id, daily_new_leads_target). The arq _job_id makes it one run per tenant per day even
if the cron fires twice. Scoring, enrichment and outreach follow by chaining and by the 5-minute outreach
tick.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from arq.cron import cron
from sqlalchemy import select

from app.config import settings as app_settings
from app.db import SessionLocal
from app.models.tenants import BusinessSettings
from app.workers.queue import enqueue

logger = logging.getLogger("app.jobs.daily")


async def due_tenants(now: datetime) -> list[tuple[str, int]]:
    """(tenant_id, daily_new_leads_target) for the tenants that source today."""
    weekday = now.astimezone(ZoneInfo(app_settings.TIMEZONE)).weekday()
    async with SessionLocal() as session:
        rows = await session.execute(
            select(
                BusinessSettings.tenant_id,
                BusinessSettings.daily_new_leads_target,
                BusinessSettings.working_days,
            ).where(
                BusinessSettings.agent_enabled.is_(True),
                BusinessSettings.onboarding_completed.is_(True),
            )
        )
        return [(str(tid), int(target)) for tid, target, days in rows if weekday in (days or [])]


async def job_daily_cycle(ctx: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    day = now.astimezone(ZoneInfo(app_settings.TIMEZONE)).date().isoformat()
    enqueued = 0
    tenants = await due_tenants(now)
    for tenant_id, target in tenants:
        try:
            await enqueue(
                "job_run_sourcing",
                tenant_id=tenant_id,
                max_results=target,
                trigger="schedule",
                _job_id=f"daily-sourcing:{tenant_id}:{day}",
            )
            enqueued += 1
        except Exception:  # one tenant must not stop the others
            logger.exception("daily cycle: could not enqueue sourcing for tenant %s", tenant_id)
    logger.info("daily cycle %s: %d/%d tenants enqueued", day, enqueued, len(tenants))
    return {"day": day, "tenants": len(tenants), "enqueued": enqueued}


# Worker timezone is Africa/Cairo (app/workers/main.py), so this is 09:00 Cairo time.
CRON_JOBS = [cron(job_daily_cycle, hour={9}, minute={0}, run_at_startup=False)]
