"""Mock ICP Builder routes: /icp/generate, /icp/active, /icp/versions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends

from app.api.icp import GenerateOut, IcpUpdateIn, IcpVersionList, IcpVersionOut, IcpVersionSummary
from app.core.errors import AppError
from app.core.security import CurrentUser
from app.mock_api.helpers import get_mock_current_user, get_tenant_settings
from app.mock_api.seed import _little_stars_icp, _little_stars_profile
from app.mock_api.state import MockAgentRun, MockAgentStep, MockIcpVersion, MockStore, get_store
from app.models.enums import AgentRunKind, AgentRunStatus, StepType
from app.schemas.agent_io import ICP, CompanyProfile

router = APIRouter(prefix="/icp", tags=["icp"])


def _summary(row: MockIcpVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "version": row.version,
        "source": row.source,
        "is_active": row.is_active,
        "notes": row.notes,
        "created_at": row.created_at,
    }


def _full(row: MockIcpVersion) -> IcpVersionOut:
    return IcpVersionOut(
        **_summary(row),
        company_profile=CompanyProfile.model_validate(row.company_profile),
        icp=ICP.model_validate(row.icp),
    )


def _create_icp_version(
    store: MockStore,
    tenant_id: uuid.UUID,
    company_profile: dict[str, Any],
    icp: dict[str, Any],
    *,
    source: str,
    notes: str | None = None,
) -> MockIcpVersion:
    existing = [v for v in store.icp_versions.values() if v.tenant_id == tenant_id]
    for v in existing:
        v.is_active = False
    next_ver = max((v.version for v in existing), default=0) + 1
    new_v = MockIcpVersion(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        version=next_ver,
        company_profile=company_profile,
        icp=icp,
        source=source,
        is_active=True,
        notes=notes,
        created_at=datetime.now(UTC),
    )
    store.icp_versions[new_v.id] = new_v
    return new_v


@router.post("/generate", response_model=GenerateOut, status_code=202)
async def generate_icp(current_user: CurrentUser = Depends(get_mock_current_user)) -> GenerateOut:
    store = get_store()
    s = get_tenant_settings(store, current_user.tenant_id)
    if not s.onboarding_completed:
        raise AppError(
            "onboarding_incomplete",
            "Finish onboarding first: the agent needs your business details to build the profile.",
            status_code=400,
        )

    now = datetime.now(UTC)
    run_id = uuid.uuid4()
    run = MockAgentRun(
        id=run_id,
        tenant_id=current_user.tenant_id,
        kind=AgentRunKind.ICP_BUILD.value,
        status=AgentRunStatus.QUEUED.value,
        trigger="manual",
        input={"company_name": s.company_name},
        created_at=now,
        started_at=now,
    )
    store.runs[run_id] = run

    # Add step 1 immediately
    step_id = uuid.uuid4()
    store.steps[step_id] = MockAgentStep(
        id=step_id,
        tenant_id=current_user.tenant_id,
        run_id=run_id,
        seq=1,
        step_type=StepType.LLM_CALL.value,
        name="icp_builder.profile",
        input={"company_name": s.company_name},
        output={"status": "synthesizing_profile"},
        model="gemini-4-hydrogen",
        input_tokens=920,
        output_tokens=340,
        cache_read_tokens=200,
        cost_usd=0.0028,
        latency_ms=650,
        created_at=now,
    )
    return GenerateOut(run_id=run_id)


def advance_icp_run(store: MockStore, run: MockAgentRun) -> None:
    """Advance an ICP_BUILD run deterministically on poll."""
    run.poll_count += 1
    now = datetime.now(UTC)
    if run.status == AgentRunStatus.QUEUED.value:
        run.status = AgentRunStatus.RUNNING.value
        return

    if run.status == AgentRunStatus.RUNNING.value:
        s = get_tenant_settings(store, run.tenant_id)
        base_profile = _little_stars_profile()
        if s.company_name:
            base_profile["company_name"] = s.company_name
        if s.description:
            base_profile["one_liner"] = s.description
        if s.products:
            base_profile["products"] = s.products
        if s.allowed_offers:
            base_profile["allowed_offers"] = s.allowed_offers
        base_profile["max_discount_percent"] = s.max_discount_percent

        base_icp = _little_stars_icp()
        if s.target_regions:
            base_icp["regions"] = s.target_regions

        new_ver = _create_icp_version(
            store,
            run.tenant_id,
            base_profile,
            base_icp,
            source="agent",
            notes="Generated via mock ICP builder",
        )
        step_id = uuid.uuid4()
        store.steps[step_id] = MockAgentStep(
            id=step_id,
            tenant_id=run.tenant_id,
            run_id=run.id,
            seq=2,
            step_type=StepType.LLM_CALL.value,
            name="icp_builder.icp",
            input={"profile_company": base_profile["company_name"]},
            output={"version": new_ver.version, "regions_count": len(base_icp["regions"])},
            model="gemini-4-hydrogen",
            input_tokens=1100,
            output_tokens=480,
            cache_read_tokens=400,
            cost_usd=0.0036,
            latency_ms=890,
            created_at=now,
        )
        run.status = AgentRunStatus.SUCCEEDED.value
        run.finished_at = now
        run.total_input_tokens = 2020
        run.total_output_tokens = 820
        run.total_cost_usd = 0.0064
        run.output_summary = {"version": new_ver.version, "icp_id": str(new_ver.id)}


@router.get("/active", response_model=IcpVersionOut | None)
async def get_active(current_user: CurrentUser = Depends(get_mock_current_user)) -> IcpVersionOut | None:
    store = get_store()
    row = next(
        (v for v in store.icp_versions.values() if v.tenant_id == current_user.tenant_id and v.is_active),
        None,
    )
    return _full(row) if row else None


@router.get("/versions", response_model=IcpVersionList)
async def get_versions(current_user: CurrentUser = Depends(get_mock_current_user)) -> IcpVersionList:
    store = get_store()
    rows = [v for v in store.icp_versions.values() if v.tenant_id == current_user.tenant_id]
    rows.sort(key=lambda r: r.version, reverse=True)
    return IcpVersionList(items=[IcpVersionSummary(**_summary(r)) for r in rows], total=len(rows))


@router.put("/active", response_model=IcpVersionOut)
async def update_active(
    body: IcpUpdateIn, current_user: CurrentUser = Depends(get_mock_current_user)
) -> IcpVersionOut:
    store = get_store()
    s = get_tenant_settings(store, current_user.tenant_id)
    if not s.onboarding_completed:
        raise AppError(
            "onboarding_incomplete",
            "Finish onboarding first: the agent needs your business details to build the profile.",
            status_code=400,
        )
    new_v = _create_icp_version(
        store,
        current_user.tenant_id,
        body.company_profile.model_dump(),
        body.icp.model_dump(),
        source="user",
        notes=body.notes,
    )
    return _full(new_v)
