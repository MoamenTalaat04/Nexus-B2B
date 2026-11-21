"""job_enrich_leads (P3-1): enrich qualified leads in bounded concurrency."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core.tracing import StepType, agent_run
from app.db import SessionLocal
from app.models.enums import AgentRunKind, LeadStatus
from app.models.leads import Lead
from app.services.enrichment import enrich_lead

logger = logging.getLogger("app.jobs.enrichment")

MAX_CONCURRENT_LEADS = 5


async def run_enrich_leads(
    session: Any,
    tenant_id: uuid.UUID,
    lead_ids: list[uuid.UUID],
    *,
    run_id: uuid.UUID | None = None,
) -> dict[str, int]:
    """Enrich selected leads, isolating one lead failure from the rest."""
    async with agent_run(
        tenant_id,
        AgentRunKind.ENRICHMENT,
        trigger="chained",
        input={"lead_ids": [str(lead_id) for lead_id in lead_ids]},
        run_id=run_id,
    ) as run:
        if not lead_ids:
            summary = {"processed": 0, "enriched": 0, "no_contact": 0, "failed": 0}
            await run.step(StepType.DECISION, "enrichment.summary", output=summary)
            run.output_summary = summary
            return summary

        rows = (
            (
                await session.execute(
                    select(Lead)
                    .where(
                        Lead.tenant_id == tenant_id,
                        Lead.id.in_(lead_ids),
                        Lead.status == LeadStatus.QUALIFIED.value,
                    )
                    .order_by(Lead.created_at.asc(), Lead.id.asc())
                )
            )
            .scalars()
            .all()
        )

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_LEADS)
        summary = {"processed": 0, "enriched": 0, "no_contact": 0, "failed": 0}

        async def process_one(lead: Lead) -> None:
            async with semaphore:
                try:
                    await enrich_lead(session, run, lead)
                    summary["processed"] += 1
                    if lead.status == LeadStatus.ENRICHED.value:
                        lead.next_action_at = datetime.now(UTC)
                        summary["enriched"] += 1
                    elif lead.status == LeadStatus.NO_CONTACT.value:
                        summary["no_contact"] += 1
                except Exception as exc:
                    summary["failed"] += 1
                    logger.exception("enrichment failed for tenant %s lead %s", tenant_id, lead.id)
                    await run.step(
                        StepType.ERROR,
                        "enrichment.lead_failed",
                        input={"lead_id": str(lead.id)},
                        output={"error": type(exc).__name__},
                        lead_id=lead.id,
                    )

        await asyncio.gather(*(process_one(lead) for lead in rows))
        await session.commit()
        await run.step(StepType.DECISION, "enrichment.summary", output=summary)
        run.output_summary = summary
        return summary


async def job_enrich_leads(
    ctx: dict[str, Any],
    tenant_id: str,
    lead_ids: list[str],
) -> dict[str, Any]:
    tid = uuid.UUID(str(tenant_id))
    lids = [uuid.UUID(str(lead_id)) for lead_id in lead_ids]
    async with SessionLocal() as session:
        summary = await run_enrich_leads(session, tid, lids)
    return {"status": "succeeded", **summary}
