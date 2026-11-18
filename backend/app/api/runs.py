"""Agent runs API (CONTRACTS section 11, P0-3): the data behind the Agent Activity page (P2-4).

GET /api/v1/runs?kind=&status=&page=&page_size=   → {"items": [run], "total": n}, newest first
GET /api/v1/runs/{id}                               → run + its steps ordered by seq
Both are scoped to the authenticated user's tenant.
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.security import CurrentUser, get_current_user
from app.db import get_session
from app.models.enums import AgentRunKind, AgentRunStatus
from app.models.runs import AgentRun, AgentStep

router = APIRouter(prefix="/runs", tags=["runs"])


class RunOut(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    trigger: str
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float

    @classmethod
    def of(cls, run: AgentRun) -> "RunOut":
        duration = None
        if run.started_at and run.finished_at:
            duration = int((run.finished_at - run.started_at).total_seconds() * 1000)
        return cls(
            id=run.id,
            kind=run.kind,
            status=run.status,
            trigger=run.trigger,
            error=run.error,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            duration_ms=duration,
            total_input_tokens=run.total_input_tokens,
            total_output_tokens=run.total_output_tokens,
            total_cost_usd=float(run.total_cost_usd),
        )


class StepOut(BaseModel):
    id: uuid.UUID
    seq: int
    step_type: str
    name: str
    input: Any
    output: Any
    model: str | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float
    latency_ms: int
    lead_id: uuid.UUID | None
    created_at: datetime


class RunDetailOut(RunOut):
    input: dict[str, Any]
    output_summary: dict[str, Any] | None
    steps: list[StepOut]


class RunListOut(BaseModel):
    items: list[RunOut]
    total: int


@router.get("", response_model=RunListOut)
async def list_runs(
    kind: AgentRunKind | None = None,
    status: AgentRunStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RunListOut:
    filters = [AgentRun.tenant_id == user.tenant_id]
    if kind is not None:
        filters.append(AgentRun.kind == kind.value)
    if status is not None:
        filters.append(AgentRun.status == status.value)
    total = (await session.execute(select(func.count()).select_from(AgentRun).where(*filters))).scalar_one()
    rows = (
        await session.execute(
            select(AgentRun)
            .where(*filters)
            .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars()
    return RunListOut(items=[RunOut.of(r) for r in rows], total=total)


@router.get("/{run_id}", response_model=RunDetailOut)
async def get_run(
    run_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RunDetailOut:
    run = (
        await session.execute(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.tenant_id == user.tenant_id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError("run")
    steps = (
        await session.execute(
            select(AgentStep)
            .where(AgentStep.run_id == run.id, AgentStep.tenant_id == user.tenant_id)
            .order_by(AgentStep.seq)
        )
    ).scalars()
    return RunDetailOut(
        **RunOut.of(run).model_dump(),
        input=run.input,
        output_summary=run.output_summary,
        steps=[
            StepOut(
                id=s.id,
                seq=s.seq,
                step_type=s.step_type,
                name=s.name,
                input=s.input,
                output=s.output,
                model=s.model,
                input_tokens=s.input_tokens,
                output_tokens=s.output_tokens,
                cache_read_tokens=s.cache_read_tokens,
                cost_usd=float(s.cost_usd),
                latency_ms=s.latency_ms,
                lead_id=s.lead_id,
                created_at=s.created_at,
            )
            for s in steps
        ],
    )
