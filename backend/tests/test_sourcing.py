"""P2-2: the sourcing job end to end (mock LLM + fake search source), POST /runs/sourcing, the daily cycle."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import PlaceResult, RegionFilter
from app.config import settings as app_settings
from app.core.tracing import create_queued_run
from app.models.enums import AgentRunKind, AgentRunStatus, StepType
from app.models.leads import Lead, SearchQuery
from app.models.runs import AgentRun, AgentStep
from app.models.tenants import BusinessSettings, Tenant
from app.schemas.agent_io import ICP, CompanyProfile, GeneratedQuery, QueryPlan, RegionTarget
from app.services import icp_service
from app.workers.jobs import daily as daily_job
from app.workers.jobs import sourcing as sourcing_job

FIXTURES = Path(__file__).parent / "fixtures" / "llm"


def auth(tenant_id: uuid.UUID) -> dict[str, str]:
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "tid": str(tenant_id), "role": "owner"}, app_settings.JWT_SECRET, "HS256"
    )
    return {"Cookie": f"access_token={token}"}


class FakeSearch:
    """3 places per city, whatever the query: the same city always returns the same place ids."""

    name = "google_places"

    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.calls: list[tuple[str, RegionFilter]] = []
        self.last_request_count = 0
        self._areas: dict[tuple[str, str], int] = {}

    async def search(self, query: str, *, region: RegionFilter, max_results: int = 20) -> list[PlaceResult]:
        self.calls.append((query, region))
        if self.fail_on and query == self.fail_on:
            raise RuntimeError("Places API 503")
        self.last_request_count = 1
        city = region.cities[0] if region.cities else "any"
        area = self._areas.setdefault((region.governorate, city), len(self._areas))
        return [
            PlaceResult(
                source="google_places",
                source_ref=f"{region.governorate}-{city}-{i}",
                name=f"محل أطفال {city} {i}",
                governorate=region.governorate,
                city=None if city == "any" else city,
                phone_national=f"010{area:04d}{i:04d}",
            )
            for i in range(3)
        ]


async def make_tenant(session: AsyncSession, *, onboarded: bool = True, icp: bool = True) -> Tenant:
    tenant = Tenant(name="Little Stars")
    session.add(tenant)
    await session.flush()
    session.add(
        BusinessSettings(
            tenant_id=tenant.id,
            company_name="Little Stars Kids Wear",
            onboarding_completed=onboarded,
            agent_enabled=True,
            daily_new_leads_target=25,
        )
    )
    await session.flush()
    if icp:
        await icp_service.save_version(
            session,
            tenant.id,
            CompanyProfile.model_validate_json((FIXTURES / "icp_builder.profile.json").read_text("utf-8")),
            ICP.model_validate_json((FIXTURES / "icp_builder.icp.json").read_text("utf-8")),
            source="agent",
        )
        await session.flush()
    return tenant


@pytest.fixture
def enqueued(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_enqueue(job_name: str, **kwargs: Any) -> str:
        calls.append((job_name, kwargs))
        return "job-id"

    monkeypatch.setattr(sourcing_job, "enqueue", fake_enqueue)
    monkeypatch.setattr("app.api.runs_trigger.enqueue", fake_enqueue)
    monkeypatch.setattr(daily_job, "enqueue", fake_enqueue)
    return calls


@pytest.fixture
def search(monkeypatch: pytest.MonkeyPatch) -> FakeSearch:
    fake = FakeSearch()
    monkeypatch.setattr(sourcing_job.registry, "get_search_source", lambda name="google_places": fake)
    return fake


@pytest.fixture
def fixed_plan(monkeypatch: pytest.MonkeyPatch) -> QueryPlan:
    """The same 3 searches every run (the real generator never repeats a recent query)."""
    plan = QueryPlan(
        queries=[
            GeneratedQuery(
                query="محل ملابس اطفال",
                region=RegionTarget(governorate="Cairo", cities=["Nasr City"]),
                rationale="r",
            ),
            GeneratedQuery(
                query="محل ملابس اطفال",
                region=RegionTarget(governorate="Cairo", cities=["Heliopolis"]),
                rationale="r",
            ),
            GeneratedQuery(
                query="kids wear", region=RegionTarget(governorate="Giza", cities=[]), rationale="r"
            ),
        ]
    )

    async def fake_generate(run: Any, **kwargs: Any) -> QueryPlan:
        return plan

    monkeypatch.setattr(sourcing_job, "generate_queries", fake_generate)
    return plan


async def lead_count(session: AsyncSession, tenant: Tenant) -> int:
    return int(
        await session.scalar(select(func.count()).select_from(Lead).where(Lead.tenant_id == tenant.id)) or 0
    )


# ---------------------------------------------------------------------------------------------- the job


async def test_sourcing_end_to_end_with_the_query_generator(
    session: AsyncSession, search: FakeSearch, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    tenant = await make_tenant(session)
    first = await sourcing_job.run_sourcing(session, tenant.id, max_results=60)
    assert first.created == 9  # 3 places in each of Nasr City, Heliopolis and Giza; the rest are duplicates
    assert first.queries_failed == 0 and first.duplicates > 0
    assert await lead_count(session, tenant) == first.created
    assert enqueued[-1] == ("job_score_leads", {"tenant_id": str(tenant.id), "run_id": str(first.run_id)})

    run = await session.get(AgentRun, first.run_id)
    assert run is not None and run.status == AgentRunStatus.SUCCEEDED.value
    assert run.output_summary is not None and run.output_summary["created"] == first.created
    steps = list(
        (
            await session.execute(select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.seq))
        ).scalars()
    )
    kinds = [s.step_type for s in steps]
    assert StepType.LLM_CALL.value in kinds and StepType.EXTERNAL_API.value in kinds
    assert steps[-1].step_type == StepType.DECISION.value and steps[-1].name == "sourcing.totals"
    queries = (await session.execute(select(SearchQuery).where(SearchQuery.run_id == run.id))).scalars().all()
    assert len(queries) == first.queries_run and all(q.results_count == 3 for q in queries)
    leads = (await session.execute(select(Lead).where(Lead.tenant_id == tenant.id))).scalars().all()
    assert all(lead.sourcing_run_id == run.id and lead.status == "new" for lead in leads)


async def test_no_duplicates_across_two_runs(
    session: AsyncSession,
    search: FakeSearch,
    fixed_plan: QueryPlan,
    enqueued: list[tuple[str, dict[str, Any]]],
) -> None:
    tenant = await make_tenant(session)
    first = await sourcing_job.run_sourcing(session, tenant.id, max_results=60)
    assert first.created == 9
    enqueued.clear()
    second = await sourcing_job.run_sourcing(session, tenant.id, max_results=60)
    assert (second.created, second.duplicates) == (0, 9)
    assert await lead_count(session, tenant) == 9
    assert enqueued == []  # nothing new to score


async def test_stops_at_max_results(
    session: AsyncSession,
    search: FakeSearch,
    fixed_plan: QueryPlan,
    enqueued: list[tuple[str, dict[str, Any]]],
) -> None:
    tenant = await make_tenant(session)
    result = await sourcing_job.run_sourcing(session, tenant.id, max_results=4)
    assert result.created == 4
    assert len(search.calls) == 2  # 3 + 1, then stop


async def test_one_failing_query_does_not_kill_the_run(
    session: AsyncSession, search: FakeSearch, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    search.fail_on = "ملابس بيبي"
    tenant = await make_tenant(session)
    result = await sourcing_job.run_sourcing(session, tenant.id, max_results=60)
    assert result.queries_failed == 1 and result.created > 0
    errors = (
        (
            await session.execute(
                select(AgentStep).where(
                    AgentStep.run_id == result.run_id, AgentStep.step_type == StepType.ERROR.value
                )
            )
        )
        .scalars()
        .all()
    )
    assert [e.name for e in errors] == ["google_places.search_failed"]


async def test_no_active_icp_fails_the_run(
    session: AsyncSession, search: FakeSearch, enqueued: list[tuple[str, dict[str, Any]]], monkeypatch: Any
) -> None:
    tenant = await make_tenant(session, icp=False)

    @asynccontextmanager
    async def test_session() -> AsyncIterator[AsyncSession]:
        yield session

    monkeypatch.setattr(sourcing_job, "SessionLocal", test_session)
    out = await sourcing_job.job_run_sourcing({}, str(tenant.id))
    assert out == {"status": "failed", "error": "no_active_icp"}
    run = (await session.execute(select(AgentRun).where(AgentRun.tenant_id == tenant.id))).scalar_one()
    assert run.status == AgentRunStatus.FAILED.value and run.error and "no_active_icp" in run.error
    assert search.calls == []


async def test_reuses_the_queued_run(
    session: AsyncSession, search: FakeSearch, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    tenant = await make_tenant(session)
    run_id = await create_queued_run(session, tenant.id, AgentRunKind.SOURCING, trigger="manual", input={})
    await session.flush()
    result = await sourcing_job.run_sourcing(session, tenant.id, max_results=5, run_id=run_id)
    assert result.run_id == run_id


# ---------------------------------------------------------------------------------------------- the API


async def test_post_sourcing_creates_a_run_and_enqueues(
    client: AsyncClient, session: AsyncSession, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    tenant = await make_tenant(session)
    resp = await client.post("/api/v1/runs/sourcing", json={"max_results": 10}, headers=auth(tenant.id))
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["run_id"]
    run = await session.get(AgentRun, uuid.UUID(run_id))
    assert run is not None and run.status == "queued" and run.kind == "sourcing"
    assert enqueued == [
        ("job_run_sourcing", {"tenant_id": str(tenant.id), "max_results": 10, "run_id": run_id})
    ]

    # the run shows up in the Agent Activity API immediately
    assert (await client.get(f"/api/v1/runs/{run_id}", headers=auth(tenant.id))).status_code == 200

    again = await client.post("/api/v1/runs/sourcing", headers=auth(tenant.id))
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "sourcing_already_running"


async def test_post_sourcing_defaults_to_daily_target(
    client: AsyncClient, session: AsyncSession, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    tenant = await make_tenant(session)
    assert (await client.post("/api/v1/runs/sourcing", headers=auth(tenant.id))).status_code == 202
    assert enqueued[0][1]["max_results"] == 25


async def test_post_sourcing_400s(
    client: AsyncClient, session: AsyncSession, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    not_onboarded = await make_tenant(session, onboarded=False)
    resp = await client.post("/api/v1/runs/sourcing", headers=auth(not_onboarded.id))
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "onboarding_incomplete"
    no_icp = await make_tenant(session, icp=False)
    resp = await client.post("/api/v1/runs/sourcing", headers=auth(no_icp.id))
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "no_active_icp"
    assert enqueued == []
    bad = await client.post("/api/v1/runs/sourcing", json={"max_results": 0}, headers=auth(no_icp.id))
    assert bad.status_code == 422


async def test_post_sourcing_tenant_isolation(
    client: AsyncClient, session: AsyncSession, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    a, b = await make_tenant(session), await make_tenant(session)
    assert (await client.post("/api/v1/runs/sourcing", headers=auth(a.id))).status_code == 202
    # A's running sourcing does not block B
    assert (await client.post("/api/v1/runs/sourcing", headers=auth(b.id))).status_code == 202
    assert {kw["tenant_id"] for _, kw in enqueued} == {str(a.id), str(b.id)}


# ---------------------------------------------------------------------------------------------- daily cycle


async def test_daily_cycle_enqueues_enabled_tenants_on_working_days(
    session: AsyncSession, enqueued: list[tuple[str, dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    on = await make_tenant(session)
    off = await make_tenant(session)
    off_settings = (
        await session.execute(select(BusinessSettings).where(BusinessSettings.tenant_id == off.id))
    ).scalar_one()
    off_settings.agent_enabled = False
    await session.flush()

    @asynccontextmanager
    async def test_session() -> AsyncIterator[AsyncSession]:
        yield session

    monkeypatch.setattr(daily_job, "SessionLocal", test_session)
    monday = datetime(2026, 11, 23, 7, 0, tzinfo=UTC)  # 09:00 Cairo
    friday = datetime(2026, 11, 27, 7, 0, tzinfo=UTC)  # not in the default working days
    ids = {tid for tid, _ in await daily_job.due_tenants(monday)}
    assert str(on.id) in ids and str(off.id) not in ids
    assert str(on.id) not in {tid for tid, _ in await daily_job.due_tenants(friday)}

    out = await daily_job.job_daily_cycle({})
    assert out["enqueued"] == out["tenants"]
    assert all(name == "job_run_sourcing" and kw["trigger"] == "schedule" for name, kw in enqueued)
    assert daily_job.CRON_JOBS and daily_job.CRON_JOBS[0].hour == {9}
