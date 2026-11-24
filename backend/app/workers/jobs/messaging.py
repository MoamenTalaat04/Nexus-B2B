"""Messaging jobs (CONTRACTS section 10, P3-2).

job_send_message(message_id)        send one queued WhatsApp message (services.messaging.send_message_in)
job_requeue_stuck_messages          cron every 10 min: re-enqueue queued messages nobody picked up
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from arq import Retry
from arq.cron import cron

from app.db import SessionLocal
from app.services import messaging

logger = logging.getLogger("app.jobs.messaging")

NOT_FOUND_RETRIES = 3
STUCK_AFTER = timedelta(minutes=10)


async def job_send_message(ctx: dict[str, Any], message_id: str) -> dict[str, Any]:
    async with SessionLocal() as session:
        outcome = await messaging.send_message_in(session, uuid.UUID(str(message_id)))
    if outcome.status == "not_found" and int(ctx.get("job_try", 1)) <= NOT_FOUND_RETRIES:
        # The creating transaction may not be committed yet: try again shortly.
        raise Retry(defer=5)
    return {"status": outcome.status, "error": outcome.error}


async def job_requeue_stuck_messages(ctx: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        ids = await messaging.stuck_queued(session, now, STUCK_AFTER)
    for message_id in ids:
        await messaging.enqueue_send(message_id)
    if ids:
        logger.info("re-enqueued %d queued messages", len(ids))
    return {"requeued": len(ids)}


CRON_JOBS = [cron(job_requeue_stuck_messages, minute=set(range(3, 60, 10)), run_at_startup=False)]
