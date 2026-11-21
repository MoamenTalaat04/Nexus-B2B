"""P4-3 reports: a small known dataset, every metric asserted exactly (CONTRACTS section 11 /reports).

Current range 2026-11-01..2026-11-10 (Cairo); previous period 2026-10-22..2026-10-31.
Times are UTC around noon, far from the Cairo day boundaries (UTC+2 in November).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.leads import Lead, LeadOutcome, LeadStatusHistory
from app.models.messaging import Message
from app.models.runs import AgentRun, AgentStep
from app.models.tenants import Tenant

RANGE = "from=2026-11-01&to=2026-11-10"


def at(month: int, day: int, hour: int = 10, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


def auth(tenant_id: uuid.UUID) -> dict[str, str]:
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "tid": str(tenant_id), "role": "owner"},
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    return {"Cookie": f"access_token={token}"}


async def add_lead(
    session: AsyncSession,
    tenant: Tenant,
    *,
    created: datetime,
    status: str,
    path: list[str],
    score: int | None,
    governorate: str = "Cairo",
    category: str = "Kids clothing",
    contacted: datetime | None = None,
) -> Lead:
    lead = Lead(
        tenant_id=tenant.id,
        name=f"Shop {uuid.uuid4().hex[:6]}",
        status=status,
        score=score,
        governorate=governorate,
        category=category,
        first_contacted_at=contacted,
        dedupe_key=f"rep-{uuid.uuid4()}",
        created_at=created,
    )
    session.add(lead)
    await session.flush()
    previous = "new"
    for step in path:
        session.add(
            LeadStatusHistory(
                tenant_id=tenant.id, lead_id=lead.id, from_status=previous, to_status=step, actor="agent"
            )
        )
        previous = step
    return lead


def message(tenant: Tenant, lead: Lead, direction: str, when: datetime, author: str = "agent") -> Message:
    inbound = direction == "inbound"
    return Message(
        tenant_id=tenant.id,
        lead_id=lead.id,
        direction=direction,
        author="lead" if inbound else author,
        kind="text",
        status="received" if inbound else "sent",
        sent_at=None if inbound else when,
        created_at=when,
    )


def run(tenant: Tenant, kind: str, cost: str, when: datetime) -> AgentRun:
    return AgentRun(
        tenant_id=tenant.id,
        kind=kind,
        status="succeeded",
        trigger="manual",
        total_cost_usd=Decimal(cost),
        created_at=when,
    )


@pytest.fixture
async def data(session: AsyncSession) -> tuple[Tenant, Tenant]:
    a, b = Tenant(name="Reports A"), Tenant(name="Reports B")
    session.add_all([a, b])
    await session.flush()
    created = at(11, 3)
    full = ["qualified", "enriched", "queued", "contacted"]

    l1 = await add_lead(
        session,
        a,
        created=created,
        status="won",
        path=[*full, "replied", "interested", "won"],
        score=9,
        contacted=at(11, 4),
    )
    l2 = await add_lead(
        session,
        a,
        created=created,
        status="later",
        path=[*full, "replied", "interested", "later"],
        score=7,
        governorate="Giza",
        contacted=at(11, 4),
    )
    l3 = await add_lead(
        session,
        a,
        created=created,
        status="lost",
        path=[*full, "lost"],
        score=6,
        category="Toys",
        contacted=at(11, 5),
    )
    await add_lead(
        session, a, created=created, status="no_contact", path=["qualified", "no_contact"], score=6
    )
    await add_lead(session, a, created=created, status="disqualified", path=["disqualified"], score=2)
    await add_lead(session, a, created=created, status="new", path=[], score=None)
    l7 = await add_lead(session, a, created=at(10, 25), status="qualified", path=["qualified"], score=8)

    session.add_all(
        [
            message(a, l1, "outbound", at(11, 4)),
            message(a, l1, "inbound", at(11, 4, 11)),  # 60 min after first contact
            message(a, l1, "outbound", at(11, 4, 11, 30)),  # agent answers in 30 min
            message(a, l2, "outbound", at(11, 4)),
            message(a, l2, "inbound", at(11, 4, 13)),  # 180 min
            message(a, l2, "outbound", at(11, 4, 14), author="human"),  # human answers in 60 min
            message(a, l3, "outbound", at(11, 5)),
            LeadOutcome(
                tenant_id=a.id, lead_id=l1.id, outcome="won", value_egp=Decimal("5000"), created_at=at(11, 6)
            ),
            LeadOutcome(tenant_id=a.id, lead_id=l3.id, outcome="lost", created_at=at(11, 7)),
            LeadOutcome(tenant_id=a.id, lead_id=l7.id, outcome="lost", created_at=at(10, 26)),
        ]
    )
    r1, r2 = run(a, "scoring", "0.03", at(11, 3)), run(a, "sourcing", "0.01", at(11, 3))
    session.add_all([r1, r2, run(a, "scoring", "0.02", at(10, 25)), run(b, "scoring", "9", at(11, 3))])
    await session.flush()
    session.add_all(
        [
            AgentStep(
                tenant_id=a.id,
                run_id=r1.id,
                seq=1,
                step_type="llm_call",
                name="s",
                model="m-fast",
                input_tokens=1000,
                output_tokens=100,
                cache_read_tokens=250,
                cost_usd=Decimal("0.03"),
                created_at=at(11, 3),
            ),
            AgentStep(
                tenant_id=a.id,
                run_id=r2.id,
                seq=1,
                step_type="llm_call",
                name="q",
                model="m-smart",
                input_tokens=1000,
                output_tokens=50,
                cost_usd=Decimal("0.01"),
                created_at=at(11, 3),
            ),
        ]
    )
    await add_lead(session, b, created=created, status="contacted", path=full, score=9, contacted=at(11, 4))
    await session.flush()
    return a, b


async def test_summary_values_and_previous_period(client: AsyncClient, data: tuple[Tenant, Tenant]) -> None:
    a, _ = data
    resp = await client.get(f"/api/v1/reports/summary?{RANGE}", headers=auth(a.id))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["previous_from"], body["previous_to"]) == ("2026-10-22", "2026-10-31")
    k = {name: kpi["value"] for name, kpi in body["kpis"].items()}
    assert k == {
        "sourced": 6,
        "scored": 5,
        "qualified": 4,
        "qualified_rate": 0.8,
        "contactable_rate": 0.75,
        "contacted": 3,
        "replied": 2,
        "reply_rate": 0.6667,
        "positive": 2,  # l2 is "later" now but passed through "interested"
        "positive_reply_rate": 0.6667,
        "lead_response_minutes": 120.0,  # median of 60 and 180
        "our_response_minutes_agent": 30.0,
        "our_response_minutes_human": 60.0,
        "won": 1,
        "lost": 1,
        "win_rate": 0.5,
        "pipeline_value_egp": 5000.0,
        "llm_cost_usd": 0.04,
        "cost_per_qualified_lead_usd": 0.01,
        "cost_per_positive_reply_usd": 0.02,
        "cache_hit_ratio": 0.125,
    }
    kpis = body["kpis"]
    assert kpis["sourced"]["previous"] == 1 and kpis["sourced"]["delta"] == 5
    assert kpis["win_rate"]["previous"] == 0.0
    assert kpis["llm_cost_usd"]["previous"] == 0.02 and kpis["llm_cost_usd"]["delta"] == 0.02
    assert kpis["reply_rate"]["previous"] is None and kpis["reply_rate"]["delta"] is None
    assert kpis["reply_rate"]["definition"]


async def test_funnel_segments_costs_timeseries(client: AsyncClient, data: tuple[Tenant, Tenant]) -> None:
    a, _ = data
    h = auth(a.id)
    funnel = (await client.get(f"/api/v1/reports/funnel?{RANGE}", headers=h)).json()
    assert [(s["stage"], s["count"]) for s in funnel["stages"]] == [
        ("sourced", 6),
        ("qualified", 4),
        ("contacted", 3),
        ("replied", 2),
        ("positive", 2),
        ("won", 1),
    ]
    assert funnel["stages"][1]["rate_from_previous"] == 0.6667

    gov = (await client.get(f"/api/v1/reports/segments?by=governorate&{RANGE}", headers=h)).json()
    assert [(r["segment"], r["contacted"], r["replied"], r["won"]) for r in gov["rows"]] == [
        ("Cairo", 2, 1, 1),
        ("Giza", 1, 1, 0),
    ]
    bands = (await client.get(f"/api/v1/reports/segments?by=score_band&{RANGE}", headers=h)).json()
    assert sorted(r["segment"] for r in bands["rows"]) == ["4-6", "7-8", "9-10"]
    bad = await client.get(f"/api/v1/reports/segments?by=name&{RANGE}", headers=h)
    assert bad.status_code == 422

    costs = (await client.get(f"/api/v1/reports/costs?{RANGE}", headers=h)).json()
    assert costs["total_cost_usd"] == 0.04 and costs["cost_is_estimated"] is True
    assert [(k["kind"], k["cost_usd"]) for k in costs["by_kind"]] == [("scoring", 0.03), ("sourcing", 0.01)]
    assert [(m["model"], m["cache_hit_ratio"]) for m in costs["models"]] == [
        ("m-fast", 0.25),
        ("m-smart", 0.0),
    ]
    assert [(d["day"], d["kind"]) for d in costs["daily"]] == [
        ("2026-11-03", "scoring"),
        ("2026-11-03", "sourcing"),
    ]

    sourced = (await client.get(f"/api/v1/reports/timeseries?metric=sourced&{RANGE}", headers=h)).json()
    assert len(sourced["points"]) == 10
    assert {p["day"]: p["value"] for p in sourced["points"] if p["value"]} == {"2026-11-03": 6}
    replies = (await client.get(f"/api/v1/reports/timeseries?metric=replies&{RANGE}", headers=h)).json()
    assert {p["day"]: p["value"] for p in replies["points"] if p["value"]} == {"2026-11-04": 2}


async def test_tenant_isolation_empty_range_and_validation(
    client: AsyncClient, data: tuple[Tenant, Tenant]
) -> None:
    _, b = data
    k = (await client.get(f"/api/v1/reports/summary?{RANGE}", headers=auth(b.id))).json()["kpis"]
    assert (k["sourced"]["value"], k["contacted"]["value"], k["llm_cost_usd"]["value"]) == (1, 1, 9.0)

    empty = (
        await client.get("/api/v1/reports/summary?from=2026-01-01&to=2026-01-05", headers=auth(b.id))
    ).json()
    assert empty["kpis"]["sourced"]["value"] == 0
    assert empty["kpis"]["reply_rate"]["value"] is None
    assert empty["kpis"]["cost_per_qualified_lead_usd"]["value"] is None

    swapped = await client.get("/api/v1/reports/summary?from=2026-11-10&to=2026-11-01", headers=auth(b.id))
    assert swapped.status_code == 422 and swapped.json()["error"]["code"] == "invalid_range"
    assert (await client.get("/api/v1/reports/summary")).status_code == 401
    default = (await client.get("/api/v1/reports/timeseries", headers=auth(b.id))).json()
    assert len(default["points"]) == 30
