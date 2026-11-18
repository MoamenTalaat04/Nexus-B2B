"""ICP API (CONTRACTS section 11, P1-3). The /icp page (P1-4) is built on these routes.

POST /api/v1/icp/generate   → 202 {run_id}; poll GET /api/v1/runs/{run_id} until it finishes
GET  /api/v1/icp/active     → the active version (with company_profile + icp), or null if there is none
GET  /api/v1/icp/versions   → {"items": [...], "total": n}, newest first, without the big JSON
PUT  /api/v1/icp/active     {company_profile, icp, notes?} → saves an edited copy as a new active version
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import CurrentUser, get_current_user
from app.core.tenancy import get_settings_for
from app.core.tracing import create_queued_run
from app.db import get_session
from app.models.enums import AgentRunKind, AgentRunStatus
from app.models.icp import IcpVersion
from app.models.runs import AgentRun
from app.schemas.agent_io import ICP, CompanyProfile
from app.services import icp_service
from app.workers.queue import enqueue

logger = logging.getLogger("app.api.icp")
router = APIRouter(prefix="/icp", tags=["icp"])


class GenerateOut(BaseModel):
    run_id: uuid.UUID


class IcpVersionSummary(BaseModel):
    id: uuid.UUID
    version: int
    source: str
    is_active: bool
    notes: str | None
    created_at: datetime


class IcpVersionOut(IcpVersionSummary):
    company_profile: CompanyProfile
    icp: ICP


class IcpVersionList(BaseModel):
    items: list[IcpVersionSummary]
    total: int


class IcpUpdateIn(BaseModel):
    company_profile: CompanyProfile
    icp: ICP
    notes: str | None = None


def _summary(row: IcpVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "version": row.version,
        "source": row.source,
        "is_active": row.is_active,
        "notes": row.notes,
        "created_at": row.created_at,
    }


def _full(row: IcpVersion) -> IcpVersionOut:
    return IcpVersionOut(
        **_summary(row),
        company_profile=CompanyProfile.model_validate(row.company_profile),
        icp=ICP.model_validate(row.icp),
    )


async def _require_onboarding(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    settings = await get_settings_for(session, tenant_id)
    if not settings.onboarding_completed:
        raise AppError(
            "onboarding_incomplete",
            "Finish onboarding first: the agent needs your business details to build the profile.",
            status_code=400,
        )


@router.post("/generate", response_model=GenerateOut, status_code=202)
async def generate_icp(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GenerateOut:
    await _require_onboarding(session, user.tenant_id)
    run_id = await create_queued_run(
        session, user.tenant_id, AgentRunKind.ICP_BUILD, trigger="manual", input={}
    )
    await session.commit()
    try:
        await enqueue("job_build_icp", tenant_id=str(user.tenant_id), run_id=str(run_id))
    except Exception as exc:
        logger.exception("could not enqueue job_build_icp")
        run = await session.get(AgentRun, run_id)
        if run is not None:
            run.status = AgentRunStatus.FAILED.value
            run.error = "The background worker queue is not reachable."
            run.finished_at = datetime.now(UTC)
            await session.commit()
        raise AppError("queue_unavailable", "Could not start the agent. Try again in a minute.", 503) from exc
    return GenerateOut(run_id=run_id)


@router.get("/active", response_model=IcpVersionOut | None)
async def get_active(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IcpVersionOut | None:
    row = await icp_service.get_active_icp(session, user.tenant_id)
    return _full(row) if row else None


@router.get("/versions", response_model=IcpVersionList)
async def get_versions(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IcpVersionList:
    rows = await icp_service.list_versions(session, user.tenant_id)
    return IcpVersionList(items=[IcpVersionSummary(**_summary(r)) for r in rows], total=len(rows))


@router.put("/active", response_model=IcpVersionOut)
async def update_active(
    body: IcpUpdateIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IcpVersionOut:
    await _require_onboarding(session, user.tenant_id)
    await icp_service.save_version(
        session, user.tenant_id, body.company_profile, body.icp, source="user", notes=body.notes
    )
    await session.commit()
    row = await icp_service.get_active_icp(session, user.tenant_id)
    assert row is not None
    return _full(row)
