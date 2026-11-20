"""Insights API: the feedback loop (CONTRACTS section 11, P4-4). D builds InsightsCard on these routes.

GET  /api/v1/insights                   → InsightsOut {active, history, latest_run, outcomes, min_outcomes}
POST /api/v1/insights/run               → 202 {run_id}; poll GET /api/v1/runs/{run_id}
                                          400 not_enough_outcomes (< 3 won/lost), 409 feedback_already_running
POST /api/v1/insights/{id}/deactivate   → InsightVersionOut (the scorer stops using it; the owner decides)
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.core.security import CurrentUser, get_current_user
from app.core.tracing import create_queued_run
from app.db import get_session
from app.models.enums import AgentRunKind, AgentRunStatus
from app.models.notifications import LearnedInsight
from app.models.runs import AgentRun
from app.services import insights as insights_service
from app.workers.queue import enqueue

logger = logging.getLogger("app.api.insights")

router = APIRouter(prefix="/insights", tags=["insights"])

STALE_AFTER = timedelta(hours=1)


class InsightVersionOut(BaseModel):
    id: uuid.UUID
    version: int
    is_active: bool
    insights: list[str]
    icp_suggestions: list[str]
    caveats: list[str]
    stats: dict[str, Any]  # compute_stats output: totals, avg_hours_to_reply, segments{segment: [rows]}
    created_at: datetime


class RunBrief(BaseModel):
    id: uuid.UUID
    status: str
    trigger: str
    created_at: datetime
    finished_at: datetime | None
    error: str | None
    output_summary: dict[str, Any] | None


class InsightsOut(BaseModel):
    active: InsightVersionOut | None
    history: list[InsightVersionOut]
    latest_run: RunBrief | None
    outcomes: int
    min_outcomes: int


class RunStartedOut(BaseModel):
    run_id: str


def to_out(row: LearnedInsight) -> InsightVersionOut:
    stats: dict[str, Any] = row.stats or {}
    return InsightVersionOut(
        id=row.id,
        version=row.version,
        is_active=row.is_active,
        insights=[str(i) for i in row.insights or []],
        icp_suggestions=[str(i) for i in stats.get("icp_suggestions") or []],
        caveats=[str(i) for i in stats.get("caveats") or []],
        stats=stats.get("computed") or {},
        created_at=row.created_at,
    )


@router.get("", response_model=InsightsOut)
async def get_insights(
    user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> InsightsOut:
    versions = await insights_service.list_versions(session, user.tenant_id)
    run = (
        await session.execute(
            select(AgentRun)
            .where(AgentRun.tenant_id == user.tenant_id, AgentRun.kind == AgentRunKind.FEEDBACK.value)
            .order_by(AgentRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    active = next((v for v in versions if v.is_active), None)
    return InsightsOut(
        active=to_out(active) if active else None,
        history=[to_out(v) for v in versions],
        latest_run=RunBrief(
            id=run.id,
            status=run.status,
            trigger=run.trigger,
            created_at=run.created_at,
            finished_at=run.finished_at,
            error=run.error,
            output_summary=run.output_summary,
        )
        if run
        else None,
        outcomes=await insights_service.outcomes_count(session, user.tenant_id),
        min_outcomes=insights_service.MIN_OUTCOMES,
    )


@router.post("/run", response_model=RunStartedOut, status_code=202)
async def run_insights(
    user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> RunStartedOut:
    count = await insights_service.outcomes_count(session, user.tenant_id)
    if count < insights_service.MIN_OUTCOMES:
        raise AppError(
            "not_enough_outcomes",
            f"Mark at least {insights_service.MIN_OUTCOMES} leads as won or lost first ({count} so far).",
            400,
        )
    busy = await session.scalar(
        select(AgentRun.id)
        .where(
            AgentRun.tenant_id == user.tenant_id,
            AgentRun.kind == AgentRunKind.FEEDBACK.value,
            AgentRun.status.in_([AgentRunStatus.QUEUED.value, AgentRunStatus.RUNNING.value]),
            AgentRun.created_at > datetime.now(UTC) - STALE_AFTER,
        )
        .limit(1)
    )
    if busy is not None:
        raise AppError("feedback_already_running", "The insights are already being updated.", 409)
    run_id = await create_queued_run(
        session, user.tenant_id, AgentRunKind.FEEDBACK, trigger="manual", input={}
    )
    await session.commit()
    try:
        await enqueue("job_feedback", tenant_id=str(user.tenant_id), run_id=str(run_id), trigger="manual")
    except Exception as exc:
        logger.exception("could not enqueue job_feedback")
        run = await session.get(AgentRun, run_id)
        if run is not None:
            run.status = AgentRunStatus.FAILED.value
            run.error = "The background worker queue is not reachable."
            run.finished_at = datetime.now(UTC)
            await session.commit()
        raise AppError(
            "queue_unavailable", "Could not start the analysis. Try again in a minute.", 503
        ) from exc
    return RunStartedOut(run_id=str(run_id))


@router.post("/{insight_id}/deactivate", response_model=InsightVersionOut)
async def deactivate_insight(
    insight_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> InsightVersionOut:
    row = await insights_service.deactivate(session, user.tenant_id, insight_id)
    if row is None:
        raise NotFoundError("insight")
    await session.commit()
    return to_out(row)
