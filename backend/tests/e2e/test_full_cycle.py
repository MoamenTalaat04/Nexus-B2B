"""P4-4: end-to-end smoke test of the whole loop, with mock adapters and the mock LLM. Runs in CI.

register → settings → knowledge → ICP → sourcing → scoring → enrichment → outreach tick → approve → send →
inbound "interested, send me the prices" (Egyptian Arabic) → classification → reply → notification →
mark won → feedback job → insights.

Steps whose owner task is not on main yet use a small, clearly marked stand-in so the chain still runs:
register (P0-4), knowledge (P1-1), scoring (P2-3), enrichment (P3-1), the reply pipeline (P3-4) and the
outcome endpoint (P4-1). When a task lands, replace its stand-in with the real call on the same test session.
"""

import importlib.util
import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

import jwt
import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import PlaceResult, RegionFilter
from app.adapters.channels.mock import MockChannelAdapter, simulate_inbound
from app.config import settings as app_settings
from app.core import lead_state
from app.models.enums import (
    ContactType,
    LeadStatus,
    MessageDirection,
    MessageKind,
    MessageStatus,
    OutreachPurpose,
    ReplyIntent,
)
from app.models.leads import Contact, Lead, LeadOutcome
from app.models.messaging import Message
from app.models.notifications import Notification
from app.models.runs import AgentRun
from app.models.tenants import BusinessSettings, Tenant, User
from app.services import insights, messaging, outreach
from app.services.notifications import notify_owner
from app.workers.jobs import feedback as feedback_job
from app.workers.jobs import icp as icp_job
from app.workers.jobs import sourcing as sourcing_job

MONDAY_NOON = datetime(2026, 11, 23, 10, 0, tzinfo=UTC)  # 12:00 Cairo, a working day
TEAM_PHONE = "+201000009001"
PHONE_ID = "1234567890123"
INTERESTED_AR = "أهلاً، أنا مهتم جداً، ابعتلي الأسعار والكتالوج لو سمحت"


def has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


class FakeSearch:
    name = "google_places"
    last_request_count = 1
    areas: ClassVar[dict[str, int]] = {}

    async def search(self, query: str, *, region: RegionFilter, max_results: int = 20) -> list[PlaceResult]:
        city = region.cities[0] if region.cities else "Giza"
        area = self.areas.setdefault(city, len(self.areas))
        return [
            PlaceResult(
                source="google_places",
                source_ref=f"e2e-{city}-{i}",
                name=f"محل أطفال {city} {i}",
                category="Children's clothing store",
                governorate=region.governorate,
                city=city,
                phone_national=f"0100000{area:02d}{i:02d}",
                rating=4.6,
                reviews_count=80,
            )
            for i in range(2)
        ]


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    MockChannelAdapter.reset()
    FakeSearch.areas = {}
    monkeypatch.setattr(app_settings, "ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(app_settings, "WHATSAPP_APP_SECRET", "")  # mock mode accepts unsigned webhooks
    monkeypatch.setattr(sourcing_job.registry, "get_search_source", lambda name="google_places": FakeSearch())
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_enqueue(job_name: str, **kwargs: Any) -> str:
        calls.append((job_name, kwargs))
        return "job"

    for target in (
        "app.api.icp.enqueue",
        "app.api.runs_trigger.enqueue",
        "app.api.webhooks_whatsapp.enqueue",
        "app.api.insights.enqueue",
        "app.services.messaging.enqueue",
        "app.workers.jobs.sourcing.enqueue",
        "app.workers.queue.enqueue",
    ):
        monkeypatch.setattr(target, fake_enqueue)
    return calls


def cookie(user_id: uuid.UUID, tenant_id: uuid.UUID) -> dict[str, str]:
    token = jwt.encode(
        {"sub": str(user_id), "tid": str(tenant_id), "role": "owner"}, app_settings.JWT_SECRET, "HS256"
    )
    return {"Cookie": f"access_token={token}"}


async def register(client: AsyncClient, session: AsyncSession) -> tuple[dict[str, str], uuid.UUID]:
    if has_module("app.api.auth"):  # P0-4
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "e2e@example.com",
                "password": "e2e-password-123",
                "full_name": "E2E Owner",
                "company_name": "Little Stars Kids Wear",
            },
        )
        assert resp.status_code in (200, 201), resp.text
        me = (await client.get("/api/v1/auth/me")).json()
        tenant_id = uuid.UUID(str(me.get("tenant_id")))
        return {}, tenant_id  # the cookie is now in the client
    # stand-in for P0-4: the same rows register creates
    tenant = Tenant(name="Little Stars Kids Wear")
    session.add(tenant)
    await session.flush()
    user = User(tenant_id=tenant.id, email="e2e@example.com", password_hash="x", full_name="E2E Owner")
    session.add(user)
    await session.flush()
    return cookie(user.id, tenant.id), tenant.id


async def test_full_cycle(
    client: AsyncClient, session: AsyncSession, _env: list[tuple[str, dict[str, Any]]]
) -> None:
    enqueued = _env

    # 1. register
    headers, tenant_id = await register(client, session)

    # 2. settings (onboarding)
    resp = await client.put(
        "/api/v1/settings",
        headers=headers,
        json={
            "company_name": "Little Stars Kids Wear",
            "description": "مصنع ملابس أطفال في العاشر من رمضان بيبيع جملة",
            "ideal_customer_text": "محلات ملابس الأطفال في القاهرة والجيزة",
            "products": [{"name": "بيجامات قطن", "price_range": "145-210 EGP", "min_order": "1 dozen"}],
            "target_regions": [
                {"governorate": "Cairo", "cities": ["Nasr City", "Heliopolis"]},
                {"governorate": "Giza"},
            ],
            "allowed_offers": "خصم لحد 10% على أول طلبية",
            "max_discount_percent": 10,
            "first_touch_mode": "api_template",
            "autonomy_mode": "approve_first_touch",
            "agent_enabled": True,
            "demo_whitelist": [TEAM_PHONE],
            "onboarding_completed": True,
        },
    )
    assert resp.status_code == 200, resp.text

    # 3. knowledge (P1-1 not on main: the ICP builder runs without files)
    # 4. ICP
    resp = await client.post("/api/v1/icp/generate", headers=headers)
    assert resp.status_code == 202, resp.text
    await icp_job.run_icp_build(session, tenant_id, run_id=uuid.UUID(resp.json()["run_id"]))
    assert (await client.get("/api/v1/icp/active", headers=headers)).json()["version"] == 1

    # 5. connect WhatsApp (mock)
    resp = await client.put(
        "/api/v1/channels/whatsapp",
        headers=headers,
        json={"phone_number_id": PHONE_ID, "waba_id": "2000000000", "access_token": "EAAG" + "e2e" * 10},
    )
    assert resp.json()["status"] == "connected"

    # 6. sourcing ("Run agent now")
    resp = await client.post("/api/v1/runs/sourcing", json={"max_results": 6}, headers=headers)
    assert resp.status_code == 202, resp.text
    result = await sourcing_job.run_sourcing(
        session, tenant_id, max_results=6, run_id=uuid.UUID(resp.json()["run_id"])
    )
    assert result.created == 6
    assert ("job_score_leads", {"tenant_id": str(tenant_id), "run_id": str(result.run_id)}) in enqueued

    # 7. scoring + 8. enrichment — stand-ins for P2-3 / P3-1
    leads = list(
        (await session.execute(select(Lead).where(Lead.tenant_id == tenant_id).order_by(Lead.name))).scalars()
    )
    for lead in leads:
        lead.score, lead.score_reasons = 8, ["kids clothing shop in a target area"]
        await lead_state.transition(
            session, lead, LeadStatus.QUALIFIED, reason="score 8 (stand-in)", actor="agent"
        )
        session.add(
            Contact(
                tenant_id=tenant_id,
                lead_id=lead.id,
                type=ContactType.MOBILE.value,
                value=str(lead.raw["phone_e164"]),
                source="google_places",
                is_primary=True,
                confidence=0.9,
            )
        )
        await lead_state.transition(
            session, lead, LeadStatus.ENRICHED, reason="mobile found (stand-in)", actor="agent"
        )
    await session.commit()

    # 9. outreach tick
    settings = (
        await session.execute(select(BusinessSettings).where(BusinessSettings.tenant_id == tenant_id))
    ).scalar_one()
    tick = await outreach.tick_tenant(session, settings, now=MONDAY_NOON)
    assert tick.created == 6, tick
    queue = (await client.get("/api/v1/outreach/queue", headers=headers)).json()
    assert queue["total"] == 6  # approve_first_touch: first touches wait for the owner

    # 10. approve + 11. send
    first = queue["items"][0]
    resp = await client.post(f"/api/v1/outreach/messages/{first['id']}/approve", headers=headers, json={})
    assert resp.status_code == 200, resp.text
    message_id = uuid.UUID(first["id"])
    assert any(name == "job_send_message" and kw["message_id"] == str(message_id) for name, kw in enqueued)
    outcome = await messaging.send_message_in(session, message_id, now=MONDAY_NOON)
    assert outcome.status == "sent", outcome
    [sent] = MockChannelAdapter.outbox
    assert sent.to == TEAM_PHONE  # demo mode: the team phone, never the lead's number
    message = await session.get(Message, message_id)
    assert message is not None
    lead = await session.get(Lead, message.lead_id)
    assert lead is not None
    await session.refresh(lead)
    assert lead.status == LeadStatus.CONTACTED.value

    # 12. inbound: "interested, send me the prices"
    resp = await client.post(
        "/api/v1/webhooks/whatsapp",
        json=simulate_inbound(phone_number_id=PHONE_ID, from_phone=TEAM_PHONE, text=INTERESTED_AR),
    )
    assert resp.json()["stored"] == 1
    inbound = (
        await session.execute(
            select(Message).where(
                Message.lead_id == lead.id, Message.direction == MessageDirection.INBOUND.value
            )
        )
    ).scalar_one()
    assert (
        "job_handle_inbound",
        {"message_id": str(inbound.id), "_job_id": f"inbound:{inbound.id}"},
    ) in enqueued
    await session.refresh(lead)
    assert lead.status == LeadStatus.REPLIED.value

    # 13. classification + 14. reply + 15. notification — stand-in for P3-4
    inbound.reply_intent = ReplyIntent.INTERESTED.value
    await lead_state.transition(
        session, lead, LeadStatus.INTERESTED, reason="interested (stand-in)", actor="agent"
    )
    reply = await messaging.create_outbound(
        session,
        tenant_id=tenant_id,
        lead_id=lead.id,
        purpose=OutreachPurpose.REPLY,
        kind=MessageKind.TEXT,
        body="أهلاً بحضرتك 🌟 البيجامات القطن من ١٤٥ لـ ٢١٠ جنيه، وأقل طلب دستة.",
        needs_approval=False,
    )
    await notify_owner(
        session,
        tenant_id=tenant_id,
        kind="hot_lead",
        title=f"{lead.name} مهتم",
        body=INTERESTED_AR,
        lead_id=lead.id,
    )
    await session.commit()
    assert (await messaging.send_message_in(session, reply.id, now=datetime.now(UTC))).status == "sent"
    assert MockChannelAdapter.outbox[-1].kind == "text" and MockChannelAdapter.outbox[-1].to == TEAM_PHONE
    notes = (
        (await session.execute(select(Notification).where(Notification.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    assert any(n.kind == "hot_lead" for n in notes)

    # 16. mark won — stand-in for P4-1's POST /leads/{id}/outcome (+ two other closed deals)
    others = [x for x in leads if x.id != lead.id][:2]
    for target, outcome_value in ((lead, "won"), (others[0], "won"), (others[1], "lost")):
        session.add(LeadOutcome(tenant_id=tenant_id, lead_id=target.id, outcome=outcome_value))
    await lead_state.transition(
        session, lead, LeadStatus.WON, reason="first order", actor="user", actor_user_id=uuid.uuid4()
    )
    await session.commit()
    assert await insights.on_outcome_recorded(session, tenant_id) is True
    assert any(name == "job_feedback" for name, _ in enqueued)

    # 17. feedback job → insights
    summary = await feedback_job.run_feedback(session, tenant_id, trigger="chained")
    assert summary["version"] == 1
    body = (await client.get("/api/v1/insights", headers=headers)).json()
    assert body["active"]["insights"] and body["active"]["stats"]["outcomes"] == 3
    assert await insights.get_active_insights(session, tenant_id) == body["active"]["insights"]

    # every agent step of the loop was traced
    kinds = set(
        (await session.execute(select(AgentRun.kind).where(AgentRun.tenant_id == tenant_id))).scalars()
    )
    assert {"icp_build", "sourcing", "outreach_tick", "feedback"} <= kinds
    statuses = (
        (await session.execute(select(Message.status).where(Message.tenant_id == tenant_id))).scalars().all()
    )
    assert MessageStatus.FAILED.value not in statuses
