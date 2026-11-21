"""P4-1 CRM routes: detail, status/pause, notes, outcome (+ feedback hook), contacts, messages, export."""

import io
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.leads import Contact, Lead, LeadOutcome, LeadStatusHistory
from app.models.messaging import Conversation, Message
from app.models.tenants import Tenant, User
from app.services import crm, messaging


def auth(user: User) -> dict[str, str]:
    token = jwt.encode(
        {"sub": str(user.id), "tid": str(user.tenant_id), "role": "owner"},
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    return {"Cookie": f"access_token={token}"}


async def make_owner(session: AsyncSession, name: str) -> User:
    tenant = Tenant(name=name)
    session.add(tenant)
    await session.flush()
    user = User(tenant_id=tenant.id, email=f"{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
    session.add(user)
    await session.flush()
    return user


async def make_lead(session: AsyncSession, user: User, *, status: str = "contacted", **kw: object) -> Lead:
    lead = Lead(
        tenant_id=user.tenant_id,
        name=kw.pop("name", "محل بيبي لاند"),
        status=status,
        score=kw.pop("score", 8),
        governorate="Cairo",
        city="Nasr City",
        category="Children's clothing store",
        dedupe_key=f"crm-{uuid.uuid4()}",
        **kw,
    )
    session.add(lead)
    await session.flush()
    return lead


@pytest.fixture
async def owners(session: AsyncSession) -> tuple[User, User]:
    return await make_owner(session, "CRM A"), await make_owner(session, "CRM B")


@pytest.fixture(autouse=True)
def no_queue(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    sent: list[str] = []

    async def fake_send(message_id: uuid.UUID, **kwargs: object) -> None:
        sent.append(str(message_id))

    monkeypatch.setattr(messaging, "enqueue_send", fake_send)
    return sent


async def test_detail_is_complete_and_tenant_scoped(
    client: AsyncClient, session: AsyncSession, owners: tuple[User, User]
) -> None:
    a, b = owners
    lead = await make_lead(session, a, score_reasons=["Kids clothing shop"])
    session.add(
        Contact(
            tenant_id=a.tenant_id,
            lead_id=lead.id,
            type="mobile",
            value="+201012345678",
            source="website",
            is_primary=True,
            confidence=0.9,
        )
    )
    session.add(
        Message(
            tenant_id=a.tenant_id,
            lead_id=lead.id,
            direction="outbound",
            author="agent",
            kind="template",
            status="sent",
            body="أهلاً",
            created_at=datetime(2026, 11, 1, tzinfo=UTC),
        )
    )
    session.add(
        Message(
            tenant_id=a.tenant_id,
            lead_id=lead.id,
            direction="inbound",
            author="lead",
            kind="text",
            status="received",
            body="مين معايا؟",
            reply_intent="question",
            created_at=datetime(2026, 11, 2, tzinfo=UTC),
        )
    )
    await session.flush()

    resp = await client.get(f"/api/v1/leads/{lead.id}", headers=auth(a))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "محل بيبي لاند" and body["score_reasons"] == ["Kids clothing shop"]
    assert [m["direction"] for m in body["messages"]] == ["outbound", "inbound"]  # chronological
    assert body["contacts"][0]["value"] == "+201012345678"
    assert body["outcome"] is None and body["notes"] == []

    other = await client.get(f"/api/v1/leads/{lead.id}", headers=auth(b))
    assert other.status_code == 404 and other.json()["error"]["code"] == "not_found"
    assert (await client.get(f"/api/v1/leads/{lead.id}")).status_code == 401


async def test_patch_status_pause_and_opt_out_is_final(
    client: AsyncClient, session: AsyncSession, owners: tuple[User, User]
) -> None:
    a, b = owners
    lead = await make_lead(session, a)
    resp = await client.patch(f"/api/v1/leads/{lead.id}", json={"status": "interested"}, headers=auth(a))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "interested"
    history = resp.json()["history"]
    assert {"to_status": "interested", "actor": "user", "reason": "manual"}.items() <= history[-1].items()

    paused = (
        await client.patch(f"/api/v1/leads/{lead.id}", json={"agent_paused": True}, headers=auth(a))
    ).json()
    assert paused["agent_paused"] is True
    # one transaction in this test, so equal timestamps: look the entry up instead of taking the last one
    assert any(h["reason"] == "agent paused by the owner" for h in paused["history"])

    assert (
        await client.patch(f"/api/v1/leads/{lead.id}", json={"status": "won"}, headers=auth(b))
    ).status_code == 404

    out = await make_lead(session, a, status="opted_out")
    blocked = await client.patch(f"/api/v1/leads/{out.id}", json={"status": "interested"}, headers=auth(a))
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "opted_out"


async def test_notes_and_outcome_call_the_feedback_loop(
    client: AsyncClient, session: AsyncSession, owners: tuple[User, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = owners
    lead = await make_lead(session, a, status="wants_offer", next_action_at=datetime.now(UTC))
    calls: list[uuid.UUID] = []

    async def fake_on_outcome(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
        calls.append(tenant_id)
        return False

    monkeypatch.setattr(crm.insights, "on_outcome_recorded", fake_on_outcome)

    note = await client.post(
        f"/api/v1/leads/{lead.id}/notes", json={"body": "  اتصل بيه الأحد  "}, headers=auth(a)
    )
    assert note.status_code == 201 and note.json()["body"] == "اتصل بيه الأحد"
    assert (
        await client.post(f"/api/v1/leads/{lead.id}/notes", json={"body": ""}, headers=auth(a))
    ).status_code == 422

    won = await client.post(
        f"/api/v1/leads/{lead.id}/outcome", json={"outcome": "won", "value_egp": 12500.5}, headers=auth(a)
    )
    assert won.status_code == 201, won.text
    assert won.json()["value_egp"] == 12500.5
    await session.refresh(lead)
    assert (lead.status, lead.agent_paused, lead.next_action_at) == ("won", True, None)
    assert calls == [a.tenant_id]

    lost = await client.post(
        f"/api/v1/leads/{lead.id}/outcome",
        json={"outcome": "lost", "value_egp": 99, "reason": "price"},
        headers=auth(a),
    )
    assert lost.json() | {"created_at": None} == {
        "outcome": "lost",
        "value_egp": None,
        "reason": "price",
        "created_at": None,
    }
    count = await session.scalar(
        select(func.count()).select_from(LeadOutcome).where(LeadOutcome.lead_id == lead.id)
    )
    assert count == 1  # replaced, not added
    detail = (await client.get(f"/api/v1/leads/{lead.id}", headers=auth(a))).json()
    assert detail["status"] == "lost" and detail["outcome"]["outcome"] == "lost" and len(detail["notes"]) == 1


async def test_contacts_normalize_and_unblock_no_contact_leads(
    client: AsyncClient, session: AsyncSession, owners: tuple[User, User]
) -> None:
    a, _ = owners
    lead = await make_lead(session, a, status="no_contact")
    url = f"/api/v1/leads/{lead.id}/contacts"

    landline = await client.post(url, json={"type": "mobile", "value": "0222345678"}, headers=auth(a))
    assert landline.status_code == 422 and landline.json()["error"]["code"] == "not_a_mobile"

    resp = await client.post(url, json={"type": "mobile", "value": "010 1234 5678"}, headers=auth(a))
    assert resp.status_code == 201, resp.text
    assert resp.json() | {"id": None} == {
        "id": None,
        "type": "mobile",
        "value": "+201012345678",
        "source": "manual",
        "is_primary": True,
        "confidence": 1.0,
    }
    await session.refresh(lead)
    assert lead.status == "enriched" and lead.next_action_at is not None
    last = (
        (
            await session.execute(
                select(LeadStatusHistory)
                .where(LeadStatusHistory.lead_id == lead.id)
                .order_by(LeadStatusHistory.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    assert last is not None and (last.to_status, last.actor) == ("enriched", "user")

    dup = await client.post(url, json={"type": "mobile", "value": "+201012345678"}, headers=auth(a))
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "contact_exists"
    second = await client.post(url, json={"type": "mobile", "value": "01112345678"}, headers=auth(a))
    assert second.json()["is_primary"] is False
    email = await client.post(url, json={"type": "email", "value": " shop@example.com "}, headers=auth(a))
    assert email.json()["value"] == "shop@example.com"


async def test_manual_message_only_inside_the_window(
    client: AsyncClient, session: AsyncSession, owners: tuple[User, User], no_queue: list[str]
) -> None:
    a, _ = owners
    lead = await make_lead(session, a, status="replied")
    url = f"/api/v1/leads/{lead.id}/messages"

    closed = await client.post(url, json={"body": "أهلاً"}, headers=auth(a))
    assert closed.status_code == 409 and closed.json()["error"]["code"] == "window_closed"

    conv = Conversation(
        tenant_id=a.tenant_id,
        lead_id=lead.id,
        channel="whatsapp",
        contact_value="+201012345678",
        window_expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    session.add(conv)
    await session.flush()
    assert (await client.post(url, json={"body": "أهلاً"}, headers=auth(a))).status_code == 409

    conv.window_expires_at = datetime.now(UTC) + timedelta(hours=5)
    await session.flush()
    sent = await client.post(url, json={"body": "  الأسعار في الكتالوج  "}, headers=auth(a))
    assert sent.status_code == 201, sent.text
    body = sent.json()
    assert (body["author"], body["kind"], body["purpose"], body["status"]) == (
        "human",
        "text",
        "reply",
        "queued",
    )
    assert body["body"] == "الأسعار في الكتالوج"
    assert no_queue == [body["id"]]

    lead.status = "opted_out"
    await session.flush()
    refused = await client.post(url, json={"body": "تاني"}, headers=auth(a))
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "opted_out"
    assert len(no_queue) == 1


async def test_export_xlsx_with_arabic_and_filters(
    client: AsyncClient, session: AsyncSession, owners: tuple[User, User]
) -> None:
    a, b = owners
    won = await make_lead(
        session,
        a,
        status="won",
        name="عالم الصغار",
        score=9,
        first_contacted_at=datetime(2026, 11, 4, 10, tzinfo=UTC),
    )
    session.add(
        Contact(
            tenant_id=a.tenant_id,
            lead_id=won.id,
            type="mobile",
            value="+201012345678",
            source="website",
            is_primary=True,
            confidence=0.9,
        )
    )
    session.add(LeadOutcome(tenant_id=a.tenant_id, lead_id=won.id, outcome="won", value_egp=5000))
    await make_lead(session, a, status="new", name="Kids Park", score=3)
    await make_lead(session, b, status="won", name="Other tenant")
    await session.flush()

    resp = await client.get("/api/v1/leads/export.xlsx", headers=auth(a))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/vnd.openxmlformats")
    ws = load_workbook(io.BytesIO(resp.content)).active
    assert ws is not None
    rows = list(ws.iter_rows(values_only=True))
    assert list(rows[0]) == crm.EXPORT_COLUMNS
    assert [r[0] for r in rows[1:]] == ["عالم الصغار", "Kids Park"]  # score desc; tenant B excluded
    first = dict(zip(crm.EXPORT_COLUMNS, rows[1], strict=True))
    assert (first["Primary mobile"], first["Outcome"], first["Value (EGP)"]) == ("+201012345678", "won", 5000)
    assert first["First contacted"] == datetime(2026, 11, 4, 12, 0)  # Cairo local time
    assert ws.freeze_panes == "A2"

    filtered = await client.get("/api/v1/leads/export.xlsx?status=won&q=الصغار", headers=auth(a))
    rows = list(load_workbook(io.BytesIO(filtered.content)).active.iter_rows(values_only=True))  # type: ignore[union-attr]
    assert [r[0] for r in rows[1:]] == ["عالم الصغار"]
