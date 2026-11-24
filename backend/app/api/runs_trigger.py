"""POST /api/v1/runs/sourcing — "Run agent now" (CONTRACTS section 11, P2-2).

Body (optional): {"max_results": 1..200}; default = settings.daily_new_leads_target.
→ 202 {"run_id": "<uuid>"}; poll GET /api/v1/runs/{run_id} (P0-3) for progress and the totals.
Errors: 400 onboarding_incomplete, 400 no_active_icp, 409 sourcing_already_running, 503 queue_unavailable.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import CurrentUser, get_current_user
from app.core.tenancy import get_settings_for
from app.core.tracing import create_queued_run
from app.db import get_session
from app.models.enums import AgentRunKind, AgentRunStatus
from app.models.runs import AgentRun
from app.services import icp_service
from app.workers.queue import enqueue

logger = logging.getLogger("app.api.runs_trigger")

router = APIRouter(prefix="/runs", tags=["runs"])

# A queued/running run older than this is treated as dead (e.g. the worker was down) and does not block.
STALE_AFTER = timedelta(hours=2)


class SourcingIn(BaseModel):
    max_results: int | None = Field(default=None, ge=1, le=200)
    mode: Literal["live", "sandbox"] = "live"


class RunStartedOut(BaseModel):
    run_id: str


@router.post("/sourcing", response_model=RunStartedOut, status_code=202)
async def start_sourcing(
    body: SourcingIn | None = Body(default=None),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RunStartedOut:
    settings = await get_settings_for(session, user.tenant_id)
    if not settings.onboarding_completed:
        raise AppError("onboarding_incomplete", "Finish onboarding before running the agent.", 400)
    if await icp_service.get_active_icp(session, user.tenant_id) is None:
        raise AppError("no_active_icp", "Generate your customer profile (ICP) before running the agent.", 400)
    busy = await session.scalar(
        select(AgentRun.id)
        .where(
            AgentRun.tenant_id == user.tenant_id,
            AgentRun.kind == AgentRunKind.SOURCING.value,
            AgentRun.status.in_([AgentRunStatus.QUEUED.value, AgentRunStatus.RUNNING.value]),
            AgentRun.created_at > datetime.now(UTC) - STALE_AFTER,
        )
        .limit(1)
    )
    if busy is not None:
        raise AppError("sourcing_already_running", "The agent is already looking for leads.", 409)

    max_results = (body.max_results if body else None) or settings.daily_new_leads_target
    mode = body.mode if body else "live"
    run_id = await create_queued_run(
        session,
        user.tenant_id,
        AgentRunKind.SOURCING,
        trigger="manual",
        input={"max_results": max_results, "mode": mode},
    )
    await session.commit()
    try:
        enqueue_kwargs: dict[str, object] = {
            "tenant_id": str(user.tenant_id),
            "max_results": max_results,
            "run_id": str(run_id),
        }
        if mode == "sandbox":
            enqueue_kwargs["mode"] = "sandbox"
        await enqueue("job_run_sourcing", **enqueue_kwargs)
    except Exception as exc:
        logger.exception("could not enqueue job_run_sourcing")
        run = await session.get(AgentRun, run_id)
        if run is not None:
            run.status = AgentRunStatus.FAILED.value
            run.error = "The background worker queue is not reachable."
            run.finished_at = datetime.now(UTC)
            await session.commit()
        raise AppError("queue_unavailable", "Could not start the agent. Try again in a minute.", 503) from exc
    return RunStartedOut(run_id=str(run_id))
