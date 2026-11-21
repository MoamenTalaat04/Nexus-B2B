"""Lead scoring job (P2-3)."""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.lead_scorer import LeadForScoring, score_leads
from app.core.lead_state import transition
from app.core.tenancy import get_settings_for
from app.core.tracing import agent_run
from app.db import SessionLocal
from app.models.enums import AgentRunKind, LeadStatus, StepType
from app.models.leads import Lead
from app.schemas.agent_io import ICP, CompanyProfile
from app.services.icp_service import get_active_icp
from app.services.insights import get_active_insights
from app.workers.queue import enqueue

logger = logging.getLogger("app.jobs.scoring")


def _lead_for_scoring(lead: Lead) -> LeadForScoring:
    raw = lead.raw if isinstance(lead.raw, dict) else {}
    types = raw.get("types")
    if not isinstance(types, list):
        types = []
    return LeadForScoring(
        id=str(lead.id),
        name=lead.name,
        category=lead.category,
        types=[str(item) for item in types if item is not None],
        address=lead.address,
        governorate=lead.governorate,
        city=lead.city,
        rating=lead.rating,
        reviews_count=lead.reviews_count,
        website=lead.website,
        business_status=raw.get("business_status") if isinstance(raw.get("business_status"), str) else None,
    )


async def run_score_leads(session: AsyncSession, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, int]:
    """Score all new leads from one sourcing run inside one tracing context."""
    async with agent_run(
        tenant_id,
        AgentRunKind.SCORING,
        trigger="chained",
        input={"run_id": str(run_id)},
    ) as run:
        active_icp = await get_active_icp(session, tenant_id)
        settings = await get_settings_for(session, tenant_id)
        insights = await get_active_insights(session, tenant_id)

        leads = list(
            (
                await session.execute(
                    select(Lead)
                    .where(
                        Lead.tenant_id == tenant_id,
                        Lead.sourcing_run_id == run_id,
                        Lead.status == LeadStatus.NEW.value,
                    )
                    .order_by(Lead.created_at.asc(), Lead.id.asc())
                )
            ).scalars()
        )

        counts = {"qualified": 0, "disqualified": 0, "unscored": 0}
        if active_icp is None:
            await run.step(
                StepType.ERROR,
                "lead_scorer.no_active_icp",
                output={"reason": "no active ICP for tenant", "leads": len(leads)},
            )
            counts["unscored"] = len(leads)
            run.output_summary = counts
            await session.commit()
            return counts

        profile = CompanyProfile.model_validate(active_icp.company_profile)
        icp = ICP.model_validate(active_icp.icp)
        lead_inputs = [_lead_for_scoring(lead) for lead in leads]
        scores = await score_leads(
            run,
            icp=icp,
            profile=profile,
            insights=insights,
            leads=lead_inputs,
        )
        score_by_id = {score.lead_ref: score for score in scores}

        qualified_ids: list[uuid.UUID] = []
        for lead in leads:
            score = score_by_id.get(str(lead.id))
            if score is None or getattr(score, "score", None) is None:
                lead.score = None
                lead.score_reasons = []
                lead.disqualify_reason = None
                lead.icp_version_id = active_icp.id
                counts["unscored"] += 1
                continue

            numeric_score = max(0, min(10, int(score.score)))
            lead.score = numeric_score
            lead.score_reasons = list(score.reasons[:4])
            lead.icp_version_id = active_icp.id

            if numeric_score >= settings.score_threshold:
                reason = score.reasons[0] if score.reasons else f"score {numeric_score}"
                lead.disqualify_reason = None
                await transition(
                    session,
                    lead,
                    LeadStatus.QUALIFIED,
                    reason=reason,
                    actor="agent",
                )
                counts["qualified"] += 1
                qualified_ids.append(lead.id)
            else:
                reason = score.reasons[0] if score.reasons else f"score {numeric_score}"
                lead.disqualify_reason = score.disqualify_reason or reason
                await transition(
                    session,
                    lead,
                    LeadStatus.DISQUALIFIED,
                    reason=reason,
                    actor="agent",
                )
                counts["disqualified"] += 1

        await session.commit()
        await run.step(StepType.DECISION, "lead_scorer.totals", output=counts)
        run.output_summary = counts

        if qualified_ids:
            try:
                await enqueue(
                    "job_enrich_leads",
                    tenant_id=str(tenant_id),
                    lead_ids=[str(lead_id) for lead_id in qualified_ids],
                )
            except Exception as exc:
                logger.exception("could not enqueue job_enrich_leads")
                await run.step(
                    StepType.ERROR,
                    "lead_scorer.enqueue_enrichment_failed",
                    output={"error": str(exc)},
                )
        return counts


async def job_score_leads(
    ctx: dict[str, Any],
    tenant_id: str,
    run_id: str,
) -> dict[str, Any]:
    tid = uuid.UUID(str(tenant_id))
    rid = uuid.UUID(str(run_id))
    async with SessionLocal() as session:
        counts = await run_score_leads(session, tid, rid)
    return {"status": "succeeded", **counts}
