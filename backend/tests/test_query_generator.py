"""P2-1: the query generator agent (mock LLM + spy), its post-processing and recent_queries()."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import query_generator as qg
from app.core.tracing import RunContext, agent_run
from app.models.enums import AgentRunKind
from app.models.leads import SearchQuery
from app.models.runs import AgentStep
from app.models.tenants import Tenant
from app.schemas.agent_io import ICP, CompanyProfile, GeneratedQuery, QueryPlan, RegionTarget

FIXTURES = Path(__file__).parent / "fixtures" / "llm"


def load(name: str, model: type[Any]) -> Any:
    return model.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def icp() -> ICP:
    return load("icp_builder.icp.json", ICP)  # Cairo (Nasr City, Heliopolis, Shubra) + Giza (any city)


@pytest.fixture
def profile() -> CompanyProfile:
    return load("icp_builder.profile.json", CompanyProfile)


@pytest.fixture
async def tenant(session: AsyncSession) -> Tenant:
    t = Tenant(name="Query test")
    session.add(t)
    await session.flush()
    return t


@pytest.fixture
async def run(tenant: Tenant) -> AsyncIterator[RunContext]:
    async with agent_run(tenant.id, AgentRunKind.SOURCING, trigger="manual", input={}) as ctx:
        yield ctx


def q(text: str, governorate: str, *cities: str) -> GeneratedQuery:
    return GeneratedQuery(
        query=text, region=RegionTarget(governorate=governorate, cities=list(cities)), rationale="r"
    )


# ---------------------------------------------------------------------------------- post-processing


def test_postprocess_keeps_icp_regions_and_drops_repeats(icp: ICP) -> None:
    plan = QueryPlan(
        queries=[
            q("محل ملابس اطفال", "Cairo", "Nasr City"),
            q("محل ملابس أطفال", "cairo", "nasr city"),  # same after normalization → duplicate
            q("محل ملابس اطفال", "Giza"),  # same text, other region → kept
            q("kids wear", "Alexandria"),  # outside the ICP
            q("baby shop", "Cairo", "Maadi"),  # city outside the ICP's Cairo cities
            q("ملابس بيبي", "Cairo", "Heliopolis", "Maadi"),  # Maadi trimmed, Heliopolis kept
            q("ملابس ولادي", "Cairo"),  # no city → the ICP's Cairo cities
            q("Kids  Wear", "Giza", "Dokki"),  # in already_used (normalized)
            q("   ", "Giza"),  # empty → ignored
        ]
    )
    cleaned, dropped = qg.postprocess(plan, icp=icp, already_used=["kids wear"])
    assert [(x.query, x.region.governorate, x.region.cities) for x in cleaned.queries] == [
        ("محل ملابس اطفال", "Cairo", ["Nasr City"]),
        ("محل ملابس اطفال", "Giza", []),
        ("ملابس بيبي", "Cairo", ["Heliopolis"]),
        ("ملابس ولادي", "Cairo", ["Nasr City", "Heliopolis", "Shubra"]),
    ]
    assert dropped == {
        "duplicate": ["محل ملابس أطفال"],
        "outside_regions": ["kids wear", "baby shop"],
        "already_used": ["Kids Wear"],
    }


def test_postprocess_caps_at_15(icp: ICP) -> None:
    plan = QueryPlan(queries=[q(f"query {i}", "Giza") for i in range(20)])
    cleaned, dropped = qg.postprocess(plan, icp=icp, already_used=[])
    assert len(cleaned.queries) == 15 and len(dropped["over_limit"]) == 5


def test_normalize_query() -> None:
    assert qg.normalize_query("  محلّ  ملابس   أطفالٌ ") == "محل ملابس اطفال"
    assert qg.normalize_query("مكتبة") == qg.normalize_query("مكتبه")
    assert qg.normalize_query("Kids WEAR") == "kids wear"


# ---------------------------------------------------------------------------------- the agent


async def test_mock_llm_returns_a_usable_plan(
    run: RunContext, session: AsyncSession, icp: ICP, profile: CompanyProfile
) -> None:
    plan = await qg.generate_queries(run, icp=icp, profile=profile, already_used=["ملابس بيبي"])
    assert 5 <= len(plan.queries) <= 15
    assert "ملابس بيبي" not in [x.query for x in plan.queries]  # the fixture has it; already_used removes it
    allowed = {"Cairo": {"Nasr City", "Heliopolis", "Shubra"}, "Giza": set()}
    for item in plan.queries:
        assert item.region.governorate in allowed
        assert (
            set(item.region.cities) <= allowed[item.region.governorate]
            or not allowed[item.region.governorate]
        )

    steps = list(
        (
            await session.execute(
                select(AgentStep).where(AgentStep.run_id == run.run_id).order_by(AgentStep.seq)
            )
        ).scalars()
    )
    assert [(s.step_type, s.name) for s in steps] == [
        ("llm_call", "query_generator.plan"),
        ("decision", "query_generator.postprocess"),
    ]
    assert steps[0].input["prompt_version"] == "query_generator@1"
    assert steps[1].output["dropped"] == {"already_used": ["ملابس بيبي"]}


async def test_prompt_layout_and_tier(
    run: RunContext, icp: ICP, profile: CompanyProfile, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []

    async def spy(run: Any, **kwargs: Any) -> QueryPlan:
        calls.append(kwargs)
        return load("query_generator.plan.json", QueryPlan)

    monkeypatch.setattr(qg, "llm_structured", spy)
    await qg.generate_queries(run, icp=icp, profile=profile, already_used=["old query 1", "old query 2"])
    (call,) = calls
    assert call["tier"] == "fast" and call["effort"] == "low" and call["name"] == "query_generator.plan"
    assert call["system"] == qg.SYSTEM
    assert "<icp>" in call["cached_context"] and "<company_profile>" in call["cached_context"]
    assert "outreach_angle" in call["cached_context"] and "old query 1" not in call["cached_context"]
    assert "- old query 1" in call["user"] and "- old query 2" in call["user"]
    assert "- Cairo (cities: Nasr City, Heliopolis, Shubra)" in call["user"]
    assert "- Giza (any city)" in call["user"]


async def test_recent_queries_newest_first_limited_and_tenant_scoped(
    session: AsyncSession, tenant: Tenant
) -> None:
    other = Tenant(name="Other")
    session.add(other)
    await session.flush()
    start = datetime(2026, 11, 1, tzinfo=UTC)
    for i in range(105):
        session.add(
            SearchQuery(
                tenant_id=tenant.id,
                source="google_places",
                query_text=f"q{i}",
                region={"governorate": "Cairo", "cities": []},
                created_at=start + timedelta(minutes=i),
            )
        )
    session.add(SearchQuery(tenant_id=other.id, source="google_places", query_text="secret", region={}))
    await session.flush()

    recent = await qg.recent_queries(session, tenant.id)
    assert len(recent) == 100
    assert recent[0] == "q104" and recent[-1] == "q5"
    assert "secret" not in recent
    assert await qg.recent_queries(session, uuid.uuid4()) == []
