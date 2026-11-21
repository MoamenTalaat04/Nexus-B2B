"""job_feedback (CONTRACTS section 10, P4-4): outcomes → stats (code) → insights (LLM) → new active version.

Triggered after every 3rd new outcome (services.insights.on_outcome_recorded) and by POST /insights/run.
Fewer than 3 outcomes → the run succeeds with output_summary {"skipped": "not_enough_outcomes"}.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import feedback as feedback_agent
from app.core.tracing import agent_run
from app.db import SessionLocal
from app.models.enums import AgentRunKind, StepType
from app.schemas.agent_io import ICP
from app.services import icp_service, insights

logger = logging.getLogger("app.jobs.feedback")


async def run_feedback(
    session: AsyncSession, tenant_id: uuid.UUID, *, run_id: uuid.UUID | None = None, trigger: str = "manual"
) -> dict[str, Any]:
    async with agent_run(tenant_id, AgentRunKind.FEEDBACK, trigger=trigger, input={}, run_id=run_id) as run:
        facts = await insights.load_facts(session, tenant_id)
        stats = insights.stats_from_facts(facts)
        await run.step(
            StepType.DECISION,
            "feedback.stats",
            output={"outcomes": stats["outcomes"], "won": stats["won"], "lost": stats["lost"]},
        )
        if stats["outcomes"] < insights.MIN_OUTCOMES:
            run.output_summary = {"skipped": "not_enough_outcomes", "outcomes": stats["outcomes"]}
            return run.output_summary
        active_icp = await icp_service.get_active_icp(session, tenant_id)
        icp = ICP.model_validate(active_icp.icp) if active_icp else None
        result = await feedback_agent.generate_insights(
            run, stats=stats, examples=insights.examples_from_facts(facts), icp=icp
        )
        row = await insights.save_version(
            session,
            tenant_id,
            insights=result.insights,
            stats={
                "computed": stats,
                "icp_suggestions": result.icp_suggestions,
                "caveats": result.caveats,
                "prompt_version": feedback_agent.PROMPT_VERSION,
                "run_id": str(run.run_id),
            },
        )
        await session.commit()
        await run.step(
            StepType.DECISION,
            "feedback.saved",
            output={"version": row.version, "insights": result.insights, "caveats": result.caveats},
        )
        run.output_summary = {
            "version": row.version,
            "insights": len(result.insights),
            "outcomes": stats["outcomes"],
        }
        return run.output_summary


async def job_feedback(
    ctx: dict[str, Any], tenant_id: str, run_id: str | None = None, trigger: str = "chained"
) -> dict[str, Any]:
    tid = uuid.UUID(str(tenant_id))
    rid = uuid.UUID(str(run_id)) if run_id else None
    async with SessionLocal() as session:
        summary = await run_feedback(session, tid, run_id=rid, trigger=trigger)
    return {"status": "succeeded", **summary}
