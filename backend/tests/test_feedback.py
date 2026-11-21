"""P4-4: the feedback loop — stats in code, insights via the (mock) LLM, versions, the /insights API."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.models.enums import AgentRunStatus, LeadStatus
from app.models.leads import Lead, LeadOutcome
from app.models.notifications import LearnedInsight
from app.models.runs import AgentRun
from app.models.tenants import Tenant
from app.services import insights
from app.workers.jobs import feedback as feedback_job

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def auth(tenant_id: uuid.UUID) -> dict[str, str]:
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "tid": str(tenant_id), "role": "owner"}, app_settings.JWT_SECRET, "HS256"
    )
    return {"Cookie": f"access_token={token}"}


@pytest.fixture
def enqueued(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_enqueue(job_name: str, **kwargs: Any) -> str:
        calls.append((job_name, kwargs))
        return "job"

    monkeypatch.setattr("app.workers.queue.enqueue", fake_enqueue)
    monkeypatch.setattr("app.api.insights.enqueue", fake_enqueue)
    return calls


async def tenant_with_outcomes(session: AsyncSession, won: int, lost: int) -> Tenant:
    tenant = Tenant(name="Feedback")
    session.add(tenant)
    await session.flush()
    for i in range(won + lost + 4):  # + 4 contacted leads without an outcome
        is_won, is_lost = i < won, won <= i < won + lost
        lead = Lead(
            tenant_id=tenant.id,
            name=f"محل {i}",
            category="Kids clothing store" if i % 2 == 0 else "Baby store",
            governorate="Cairo" if i % 3 else "Giza",
            city="Nasr City",
            score=8 if is_won else 5,
            rating=4.6 if is_won else 3.9,
            reviews_count=120 if is_won else 5,
            website="https://x.example" if i % 2 == 0 else None,
            status=(LeadStatus.WON if is_won else LeadStatus.LOST if is_lost else LeadStatus.CONTACTED).value,
            first_contacted_at=NOW - timedelta(days=5),
            last_inbound_at=NOW - timedelta(days=4) if (is_won or i % 2 == 0) else None,
            dedupe_key=f"k{i}",
        )
        session.add(lead)
        await session.flush()
        if is_won or is_lost:
            session.add(
                LeadOutcome(
                    tenant_id=tenant.id,
                    lead_id=lead.id,
                    outcome="won" if is_won else "lost",
                    value_egp=Decimal("15000.00") if is_won else None,
                    reason="طلب أول 10 دستة" if is_won else "السعر عالي — رقمه 01012345678",
                )
            )
    await session.flush()
    return tenant


# ---------------------------------------------------------------------------------------------- stats


def test_bands() -> None:
    assert [insights.score_band(s) for s in (None, 0, 3, 4, 6, 7, 8, 9, 10)] == [
        "unscored",
        "0-3",
        "0-3",
        "4-6",
        "4-6",
        "7-8",
        "7-8",
        "9-10",
        "9-10",
    ]
    assert insights.rating_band(None) == "no rating" and insights.rating_band(4.5) == "4.5+"
    assert insights.reviews_band(9) == "0-9" and insights.reviews_band(50) == "50-199"


async def test_stats_are_computed_in_code(session: AsyncSession) -> None:
    tenant = await tenant_with_outcomes(session, won=6, lost=4)
    stats = await insights.compute_stats(session, tenant.id)
    assert (stats["outcomes"], stats["won"], stats["lost"], stats["win_rate"]) == (10, 6, 4, 0.6)
    assert stats["won_value_egp"] == 90000.0
    assert stats["contacted"] == 14
    bands = {row["value"]: row for row in stats["segments"]["score_band"]}
    assert bands["7-8"]["won"] == 6 and bands["7-8"]["win_rate"] == 1.0
    assert bands["4-6"]["lost"] == 4
    assert set(stats["segments"]) == {
        "category",
        "governorate",
        "score_band",
        "rating_band",
        "reviews_band",
        "website",
    }
    assert stats["avg_hours_to_reply"]["won"] == 24.0


async def test_examples_have_no_phone_numbers(session: AsyncSession) -> None:
    tenant = await tenant_with_outcomes(session, won=6, lost=4)
    examples = insights.examples_from_facts(await insights.load_facts(session, tenant.id))
    assert len(examples) == 10 and {e["outcome"] for e in examples} == {"won", "lost"}
    assert "01012345678" not in str(examples)  # a phone typed into the lost reason is masked


# ---------------------------------------------------------------------------------------------- the job


async def test_skips_with_fewer_than_three_outcomes(session: AsyncSession) -> None:
    tenant = await tenant_with_outcomes(session, won=1, lost=1)
    summary = await feedback_job.run_feedback(session, tenant.id)
    assert summary["skipped"] == "not_enough_outcomes"
    assert await insights.get_active_insights(session, tenant.id) == []


async def test_job_saves_new_active_versions(session: AsyncSession) -> None:
    tenant = await tenant_with_outcomes(session, won=6, lost=4)
    first = await feedback_job.run_feedback(session, tenant.id)
    assert first["version"] == 1
    active = await insights.get_active_insights(session, tenant.id)
    assert 3 <= len(active) <= 7 and any("Nasr City" in i for i in active)
    second = await feedback_job.run_feedback(session, tenant.id)
    assert second["version"] == 2
    rows = await insights.list_versions(session, tenant.id)
    assert [(r.version, r.is_active) for r in rows] == [(2, True), (1, False)]
    assert rows[0].stats["computed"]["outcomes"] == 10
    assert rows[0].stats["prompt_version"] == "feedback@1"
    run = (
        (
            await session.execute(
                select(AgentRun).where(AgentRun.tenant_id == tenant.id).order_by(AgentRun.created_at)
            )
        )
        .scalars()
        .first()
    )
    assert run is not None and run.kind == "feedback" and run.status == AgentRunStatus.SUCCEEDED.value


async def test_on_outcome_recorded_every_third(
    session: AsyncSession, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    tenant = await tenant_with_outcomes(session, won=2, lost=0)
    assert await insights.on_outcome_recorded(session, tenant.id) is False
    lead = Lead(tenant_id=tenant.id, name="جديد", status=LeadStatus.WON.value, dedupe_key="new")
    session.add(lead)
    await session.flush()
    session.add(LeadOutcome(tenant_id=tenant.id, lead_id=lead.id, outcome="won"))
    await session.flush()
    assert await insights.on_outcome_recorded(session, tenant.id) is True
    assert enqueued == [
        (
            "job_feedback",
            {"tenant_id": str(tenant.id), "trigger": "chained", "_job_id": f"feedback:{tenant.id}:3"},
        )
    ]


# ---------------------------------------------------------------------------------------------- the API


async def test_api_run_get_and_deactivate(
    client: AsyncClient, session: AsyncSession, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    tenant = await tenant_with_outcomes(session, won=6, lost=4)
    empty = (await client.get("/api/v1/insights", headers=auth(tenant.id))).json()
    assert empty["active"] is None and empty["outcomes"] == 10 and empty["min_outcomes"] == 3

    resp = await client.post("/api/v1/insights/run", headers=auth(tenant.id))
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]
    assert enqueued[-1] == (
        "job_feedback",
        {"tenant_id": str(tenant.id), "run_id": run_id, "trigger": "manual"},
    )
    assert (await client.post("/api/v1/insights/run", headers=auth(tenant.id))).status_code == 409

    await feedback_job.run_feedback(session, tenant.id, run_id=uuid.UUID(run_id))
    body = (await client.get("/api/v1/insights", headers=auth(tenant.id))).json()
    assert body["active"]["version"] == 1 and body["active"]["insights"]
    assert body["active"]["caveats"] and body["active"]["stats"]["outcomes"] == 10
    assert body["latest_run"]["id"] == run_id and body["latest_run"]["status"] == "succeeded"

    insight_id = body["active"]["id"]
    off = await client.post(f"/api/v1/insights/{insight_id}/deactivate", headers=auth(tenant.id))
    assert off.status_code == 200 and off.json()["is_active"] is False
    assert await insights.get_active_insights(session, tenant.id) == []


async def test_api_not_enough_outcomes_and_isolation(
    client: AsyncClient, session: AsyncSession, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    small = await tenant_with_outcomes(session, won=1, lost=0)
    resp = await client.post("/api/v1/insights/run", headers=auth(small.id))
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "not_enough_outcomes"

    owner = await tenant_with_outcomes(session, won=3, lost=1)
    await feedback_job.run_feedback(session, owner.id)
    row = (
        await session.execute(select(LearnedInsight).where(LearnedInsight.tenant_id == owner.id))
    ).scalar_one()
    other = await client.post(f"/api/v1/insights/{row.id}/deactivate", headers=auth(small.id))
    assert other.status_code == 404
    assert (await client.get("/api/v1/insights", headers=auth(small.id))).json()["history"] == []
