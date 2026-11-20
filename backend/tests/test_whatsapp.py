"""P3-2: the WhatsApp channel — Cloud API adapter (respx), messaging service, webhook, channels API."""

import json
import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any

import httpx
import jwt
import pytest
import respx
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import registry
from app.adapters.channels import whatsapp_cloud as wa
from app.adapters.channels.mock import MockChannelAdapter, simulate_inbound, simulate_status
from app.config import settings as app_settings
from app.core.crypto import decrypt_json
from app.models.enums import (
    ContactType,
    LeadStatus,
    MessageAuthor,
    MessageKind,
    MessageStatus,
    OutreachPurpose,
)
from app.models.leads import Contact, Lead
from app.models.messaging import ChannelConnection, Conversation, DemoRoute, Message, MessageTemplate
from app.models.notifications import Notification
from app.models.runs import AgentStep
from app.models.tenants import BusinessSettings, Tenant
from app.services import messaging

PHONE_ID = "1098765432101"
SECRET = "test-app-secret"
MONDAY_NOON = datetime(2026, 11, 23, 10, 0, tzinfo=UTC)  # 12:00 Cairo, a working day
MONDAY_NIGHT = datetime(2026, 11, 23, 20, 30, tzinfo=UTC)  # 22:30 Cairo
WHITELIST = ["+201000000001", "+201000000002"]


def auth(tenant_id: uuid.UUID, role: str = "owner") -> dict[str, str]:
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "tid": str(tenant_id), "role": role}, app_settings.JWT_SECRET, "HS256"
    )
    return {"Cookie": f"access_token={token}"}


@pytest.fixture(autouse=True)
def _mock_channel(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Fresh mock outbox, a Fernet key, the app secret, and a recording enqueue."""
    MockChannelAdapter.reset()
    monkeypatch.setattr(app_settings, "ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(app_settings, "WHATSAPP_APP_SECRET", SECRET)
    monkeypatch.setattr(app_settings, "WHATSAPP_VERIFY_TOKEN", "verify-me")
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_enqueue(job_name: str, **kwargs: Any) -> str:
        calls.append((job_name, kwargs))
        return "job"

    monkeypatch.setattr(messaging, "enqueue", fake_enqueue)
    monkeypatch.setattr("app.api.webhooks_whatsapp.enqueue", fake_enqueue)
    return calls


@pytest.fixture
def enqueued(_mock_channel: list[tuple[str, dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
    return _mock_channel


async def setup_tenant(
    session: AsyncSession,
    *,
    demo: bool = True,
    whitelist: list[str] | None = None,
    cap: int = 20,
    phone_id: str = PHONE_ID,
) -> Tenant:
    tenant = Tenant(name="WA test")
    session.add(tenant)
    await session.flush()
    session.add(
        BusinessSettings(
            tenant_id=tenant.id,
            company_name="Little Stars",
            demo_mode=demo,
            demo_whitelist=WHITELIST if whitelist is None else whitelist,
            daily_send_cap=cap,
            quiet_hours_start=time(10, 0),
            quiet_hours_end=time(20, 0),
            onboarding_completed=True,
        )
    )
    session.add(
        ChannelConnection(
            tenant_id=tenant.id,
            channel="whatsapp",
            status="connected",
            config={
                "phone_number_id": phone_id,
                "waba_id": "2000",
                "display_phone_number": "+20 100 000 0000",
            },
        )
    )
    session.add_all(
        [
            MessageTemplate(
                tenant_id=tenant.id,
                name="intro",
                language="ar",
                purpose="intro",
                body_text="أهلاً {{1}} معاك {{2}}",
                param_count=2,
                status="approved",
            ),
            MessageTemplate(
                tenant_id=tenant.id,
                name="followup",
                language="ar",
                purpose="followup",
                body_text="أهلاً تاني {{1}}",
                param_count=1,
                status="approved",
            ),
        ]
    )
    await session.flush()
    return tenant


async def make_lead(
    session: AsyncSession,
    tenant: Tenant,
    *,
    status: LeadStatus = LeadStatus.QUEUED,
    mobile: str | None = None,
) -> Lead:
    lead = Lead(tenant_id=tenant.id, name="روز كيدز", status=status.value, dedupe_key=str(uuid.uuid4()))
    session.add(lead)
    await session.flush()
    session.add(
        Contact(
            tenant_id=tenant.id,
            lead_id=lead.id,
            type=ContactType.MOBILE.value,
            value=mobile or f"+20101{uuid.uuid4().int % 10**7:07d}",
            source="google_places",
            is_primary=True,
        )
    )
    await session.flush()
    return lead


async def queued_template(session: AsyncSession, tenant: Tenant, lead: Lead, **kw: Any) -> Message:
    return await messaging.create_outbound(
        session,
        tenant_id=tenant.id,
        lead_id=lead.id,
        purpose=kw.get("purpose", OutreachPurpose.FIRST_TOUCH),
        kind=kw.get("kind", MessageKind.TEMPLATE),
        body="أهلاً روز كيدز معاك ليتل ستارز",
        template_name="intro",
        template_params=["روز كيدز", "ليتل ستارز"],
        needs_approval=kw.get("needs_approval", False),
        author=kw.get("author", MessageAuthor.AGENT),
    )


async def post_webhook(client: AsyncClient, payload: dict[str, Any], secret: str = SECRET) -> httpx.Response:
    raw = json.dumps(payload).encode()
    return await client.post(
        "/api/v1/webhooks/whatsapp",
        content=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": wa.sign(raw, secret)},
    )


# ============================================================================ adapter (Graph API, respx)

GRAPH = f"https://graph.facebook.com/{wa.DEFAULT_GRAPH_VERSION}"


@pytest.fixture
def adapter(monkeypatch: pytest.MonkeyPatch) -> wa.WhatsAppCloudAdapter:
    monkeypatch.setattr(app_settings, "WHATSAPP_GRAPH_VERSION", "")
    a = wa.WhatsAppCloudAdapter(phone_number_id=PHONE_ID, waba_id="2000", access_token="EAAG" + "x" * 30)

    async def no_sleep(_: float) -> None:
        return None

    a._sleep = no_sleep  # type: ignore[method-assign]
    return a


@respx.mock
async def test_send_template_body_and_sanitized_params(adapter: wa.WhatsAppCloudAdapter) -> None:
    route = respx.post(f"{GRAPH}/{PHONE_ID}/messages").mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})
    )
    result = await adapter.send_template(
        to="+201012345678", template_name="intro", language="ar", params=["روز\nكيدز", "a\tb      c"]
    )
    assert result.ok and result.provider_message_id == "wamid.1"
    body = json.loads(route.calls[0].request.content)
    assert body["to"] == "201012345678" and body["type"] == "template"
    assert body["template"]["language"] == {"code": "ar"}
    params = body["template"]["components"][0]["parameters"]
    assert [p["text"] for p in params] == ["روز كيدز", "a b    c"]
    assert route.calls[0].request.headers["Authorization"].startswith("Bearer EAAG")


@respx.mock
async def test_send_text_window_closed_maps_error(adapter: wa.WhatsAppCloudAdapter) -> None:
    respx.post(f"{GRAPH}/{PHONE_ID}/messages").mock(
        return_value=httpx.Response(
            400, json={"error": {"message": "(#131047) Re-engagement message", "code": 131047}}
        )
    )
    result = await adapter.send_text(to="+201012345678", body="hi")
    assert not result.ok and result.error == "window_closed"


@pytest.mark.parametrize(
    ("code", "short"),
    [
        (190, "invalid_token"),
        (131030, "recipient_not_allowed"),
        (132001, "template_not_approved"),
        (130429, "rate_limited"),
    ],
)
@respx.mock
async def test_error_codes(adapter: wa.WhatsAppCloudAdapter, code: int, short: str) -> None:
    respx.post(f"{GRAPH}/{PHONE_ID}/messages").mock(
        return_value=httpx.Response(400, json={"error": {"message": "x", "code": code}})
    )
    result = await adapter.send_template(to="+201012345678", template_name="intro", language="ar", params=[])
    assert result.error == short


@respx.mock
async def test_retries_5xx_and_429_only(adapter: wa.WhatsAppCloudAdapter) -> None:
    route = respx.post(f"{GRAPH}/{PHONE_ID}/messages").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(429, json={"error": {"code": 130429, "message": "rate"}}),
            httpx.Response(200, json={"messages": [{"id": "wamid.2"}]}),
        ]
    )
    assert (await adapter.send_text(to="+201012345678", body="x")).ok
    assert len(route.calls) == 3
    bad = respx.post(f"{GRAPH}/{PHONE_ID}/messages").mock(
        return_value=httpx.Response(400, json={"error": {"code": 100, "message": "bad"}})
    )
    before = len(bad.calls)  # respx reuses the same route for the same URL, so count only the new calls
    await adapter.send_text(to="+201012345678", body="x")
    assert len(bad.calls) - before == 1  # a 4xx is final


@respx.mock
async def test_check_connection_and_templates(adapter: wa.WhatsAppCloudAdapter) -> None:
    respx.get(f"{GRAPH}/{PHONE_ID}").mock(
        return_value=httpx.Response(200, json={"display_phone_number": "+1 555 0100", "verified_name": "LS"})
    )
    assert await adapter.check_connection() == (True, "+1 555 0100")
    respx.get(f"{GRAPH}/2000/message_templates").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "name": "intro",
                        "language": "ar",
                        "status": "APPROVED",
                        "category": "MARKETING",
                        "components": [{"type": "BODY", "text": "أهلاً {{1}} معاك {{2}} و {{1}}"}],
                    }
                ]
            },
        )
    )
    [template] = await adapter.list_templates()
    assert (template.name, template.param_count, template.status) == ("intro", 2, "APPROVED")


@respx.mock
async def test_check_connection_invalid_token(adapter: wa.WhatsAppCloudAdapter) -> None:
    respx.get(f"{GRAPH}/{PHONE_ID}").mock(
        return_value=httpx.Response(
            401, json={"error": {"code": 190, "message": "Error validating access token"}}
        )
    )
    ok, detail = await adapter.check_connection()
    assert not ok and detail.startswith("invalid_token")


def test_token_not_in_repr(adapter: wa.WhatsAppCloudAdapter) -> None:
    assert "EAAG" not in repr(adapter)


# ================================================================================ webhook


async def test_verify_handshake(client: AsyncClient) -> None:
    ok = await client.get(
        "/api/v1/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "12345"},
    )
    assert ok.status_code == 200 and ok.text == "12345"
    bad = await client.get(
        "/api/v1/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "12345"},
    )
    assert bad.status_code == 403


async def test_signature_valid_and_invalid(client: AsyncClient, session: AsyncSession) -> None:
    await setup_tenant(session)
    payload = simulate_inbound(phone_number_id=PHONE_ID, from_phone="+201099999999", text="hi")
    assert (await post_webhook(client, payload)).status_code == 200
    assert (await post_webhook(client, payload, secret="wrong")).status_code == 401
    unsigned = await client.post("/api/v1/webhooks/whatsapp", json=payload)
    assert unsigned.status_code == 401


async def test_inbound_from_contact_opens_window_and_replied(
    client: AsyncClient, session: AsyncSession, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    tenant = await setup_tenant(session, demo=False)
    lead = await make_lead(session, tenant, status=LeadStatus.CONTACTED, mobile="+201011112222")
    ts = datetime.now(UTC).replace(microsecond=0)
    payload = simulate_inbound(
        phone_number_id=PHONE_ID,
        from_phone="+201011112222",
        text="ابعتلي الأسعار",
        message_id="wamid.in.1",
        timestamp=ts,
    )
    body = (await post_webhook(client, payload)).json()
    assert body["stored"] == 1
    msg = (
        await session.execute(select(Message).where(Message.provider_message_id == "wamid.in.1"))
    ).scalar_one()
    assert (msg.direction, msg.author, msg.status) == ("inbound", "lead", "received")
    await session.refresh(lead)
    assert lead.status == LeadStatus.REPLIED.value and lead.last_inbound_at == ts
    conv = (await session.execute(select(Conversation).where(Conversation.lead_id == lead.id))).scalar_one()
    assert conv.window_expires_at == ts + timedelta(hours=24)
    assert ("job_handle_inbound", {"message_id": str(msg.id), "_job_id": f"inbound:{msg.id}"}) in enqueued


async def test_inbound_is_idempotent(
    client: AsyncClient, session: AsyncSession, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    tenant = await setup_tenant(session, demo=False)
    await make_lead(session, tenant, status=LeadStatus.CONTACTED, mobile="+201011112223")
    payload = simulate_inbound(
        phone_number_id=PHONE_ID, from_phone="+201011112223", text="hi", message_id="wamid.x"
    )
    await post_webhook(client, payload)
    again = (await post_webhook(client, payload)).json()
    assert again["stored"] == 0 and again["duplicates"] == 1
    rows = (
        (await session.execute(select(Message).where(Message.provider_message_id == "wamid.x")))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert sum(1 for name, _ in enqueued if name == "job_handle_inbound") == 1


@pytest.mark.parametrize(
    "text",
    [
        "STOP",
        "stop",
        "إلغاء",
        "الغاء",
        "بطلوا تبعتوا رسايل",
        "متبعتليش تاني لو سمحت",
        "مش عايز رسايل",
        "كفاية",
    ],
)
async def test_stop_words_opt_out_first(client: AsyncClient, session: AsyncSession, text: str) -> None:
    tenant = await setup_tenant(session, demo=False)
    lead = await make_lead(session, tenant, status=LeadStatus.CONTACTED, mobile="+201011113333")
    pending = await queued_template(
        session, tenant, lead, purpose=OutreachPurpose.FOLLOWUP, needs_approval=True
    )
    await post_webhook(
        client, simulate_inbound(phone_number_id=PHONE_ID, from_phone="+201011113333", text=text)
    )
    await session.refresh(lead)
    await session.refresh(pending)
    assert lead.status == LeadStatus.OPTED_OUT.value
    assert pending.status == MessageStatus.BLOCKED.value and pending.error == "opted_out"


@pytest.mark.parametrize(
    "text", ["عايز الغي الطلب القديم واعمل طلب جديد بكمية اكبر", "the stop near my shop is far"]
)
def test_not_every_mention_is_an_opt_out(text: str) -> None:
    assert not messaging.is_stop_message(text)


async def test_unknown_sender_notifies(client: AsyncClient, session: AsyncSession) -> None:
    tenant = await setup_tenant(session, demo=False)
    body = (
        await post_webhook(
            client, simulate_inbound(phone_number_id=PHONE_ID, from_phone="+201055555555", text="hello")
        )
    ).json()
    assert body["unknown"] == 1
    note = (
        await session.execute(select(Notification).where(Notification.tenant_id == tenant.id))
    ).scalar_one()
    assert note.title == "Message from an unknown number"


async def test_lead_initiated_chat_by_ref_code(client: AsyncClient, session: AsyncSession) -> None:
    tenant = await setup_tenant(session, demo=False)
    lead = await make_lead(session, tenant, status=LeadStatus.CONTACTED)
    text = f"أهلاً، حابب أعرف أكتر عن منتجاتكم #{lead.ref_code.lower()}"
    body = (
        await post_webhook(
            client, simulate_inbound(phone_number_id=PHONE_ID, from_phone="+201277777777", text=text)
        )
    ).json()
    assert body["stored"] == 1
    contact = (
        await session.execute(
            select(Contact).where(Contact.lead_id == lead.id, Contact.value == "+201277777777")
        )
    ).scalar_one()
    assert contact.source == "lead_initiated" and contact.type == "mobile"
    conv = (await session.execute(select(Conversation).where(Conversation.lead_id == lead.id))).scalar_one()
    assert conv.window_expires_at is not None


async def test_non_text_message_is_stored_with_a_label(client: AsyncClient, session: AsyncSession) -> None:
    tenant = await setup_tenant(session, demo=False)
    lead = await make_lead(session, tenant, status=LeadStatus.CONTACTED, mobile="+201011114444")
    payload = simulate_inbound(phone_number_id=PHONE_ID, from_phone="+201011114444", text="", kind="image")
    await post_webhook(client, payload)
    msg = (await session.execute(select(Message).where(Message.lead_id == lead.id))).scalar_one()
    assert msg.body == "[image]"


async def test_tenant_routing_by_phone_number_id(client: AsyncClient, session: AsyncSession) -> None:
    a = await setup_tenant(session, demo=False, phone_id="111111111")
    b = await setup_tenant(session, demo=False, phone_id="222222222")
    lead_a = await make_lead(session, a, status=LeadStatus.CONTACTED, mobile="+201088888888")
    lead_b = await make_lead(session, b, status=LeadStatus.CONTACTED, mobile="+201088888888")
    await post_webhook(
        client, simulate_inbound(phone_number_id="222222222", from_phone="+201088888888", text="hi")
    )
    assert (await session.execute(select(Message).where(Message.lead_id == lead_b.id))).scalar_one()
    assert (
        await session.execute(select(Message).where(Message.lead_id == lead_a.id))
    ).scalar_one_or_none() is None


# ================================================================================ sending


async def test_demo_routing_round_trip(client: AsyncClient, session: AsyncSession) -> None:
    tenant = await setup_tenant(session)
    lead_x = await make_lead(session, tenant, mobile="+201012345678")
    lead_y = await make_lead(session, tenant, mobile="+201087654321")
    mx = await queued_template(session, tenant, lead_x)
    my = await queued_template(session, tenant, lead_y)
    assert (await messaging.send_message_in(session, mx.id, now=MONDAY_NOON)).status == "sent"
    assert (await messaging.send_message_in(session, my.id, now=MONDAY_NOON)).status == "sent"
    await session.refresh(mx)
    await session.refresh(my)
    # the real numbers are never used; each lead gets its own whitelisted phone
    assert {r.to for r in MockChannelAdapter.outbox} == set(WHITELIST)
    assert mx.redirected_to != my.redirected_to and {mx.redirected_to, my.redirected_to} == set(WHITELIST)
    # an inbound from X's test phone maps back to X
    await post_webhook(
        client, simulate_inbound(phone_number_id=PHONE_ID, from_phone=str(mx.redirected_to), text="مهتم")
    )
    inbound = (
        await session.execute(
            select(Message).where(Message.lead_id == lead_x.id, Message.direction == "inbound")
        )
    ).scalar_one()
    assert inbound.redirected_to == mx.redirected_to
    await session.refresh(lead_x)
    assert lead_x.status == LeadStatus.REPLIED.value  # QUEUED → CONTACTED on send, then REPLIED


async def test_demo_route_reused_for_the_same_lead_and_lru_for_new(session: AsyncSession) -> None:
    tenant = await setup_tenant(session)
    settings = (
        await session.execute(select(BusinessSettings).where(BusinessSettings.tenant_id == tenant.id))
    ).scalar_one()
    leads = [await make_lead(session, tenant) for _ in range(3)]
    first = await messaging.route_demo(session, settings, leads[0].id)
    assert await messaging.route_demo(session, settings, leads[0].id) == first
    second = await messaging.route_demo(session, settings, leads[1].id)
    assert second != first
    third = await messaging.route_demo(session, settings, leads[2].id)  # the least recently used phone
    assert third == first
    route = (await session.execute(select(DemoRoute).where(DemoRoute.test_phone == first))).scalar_one()
    assert route.lead_id == leads[2].id


async def test_send_success_updates_lead_and_traces(session: AsyncSession) -> None:
    tenant = await setup_tenant(session)
    lead = await make_lead(session, tenant)
    message = await queued_template(session, tenant, lead)
    outcome = await messaging.send_message_in(session, message.id, now=MONDAY_NOON)
    assert outcome.status == "sent"
    await session.refresh(message)
    await session.refresh(lead)
    assert message.provider_message_id and message.sent_at == MONDAY_NOON
    assert lead.status == LeadStatus.CONTACTED.value and lead.first_contacted_at == MONDAY_NOON
    [sent] = MockChannelAdapter.outbox
    assert (sent.template_name, sent.params) == ("intro", ["روز كيدز", "ليتل ستارز"])
    step = (
        await session.execute(
            select(AgentStep).where(AgentStep.tenant_id == tenant.id, AgentStep.name == "whatsapp.send")
        )
    ).scalar_one()
    dumped = json.dumps(step.input, ensure_ascii=False)
    assert "أهلاً" not in dumped  # no body in the trace
    assert "+201000000001" not in dumped and "001" in dumped  # masked phone


async def test_opted_out_is_never_sent(session: AsyncSession) -> None:
    tenant = await setup_tenant(session)
    lead = await make_lead(session, tenant, status=LeadStatus.CONTACTED)
    message = await queued_template(session, tenant, lead, purpose=OutreachPurpose.FOLLOWUP)
    lead.status = LeadStatus.OPTED_OUT.value  # test setup only (simulates a concurrent opt-out)
    await session.flush()
    outcome = await messaging.send_message_in(session, message.id, now=MONDAY_NOON)
    assert (outcome.status, outcome.error) == ("blocked", "opted_out")
    assert MockChannelAdapter.outbox == []
    # create_outbound refuses too
    blocked = await queued_template(session, tenant, lead)
    assert blocked.status == MessageStatus.BLOCKED.value


async def test_daily_cap(session: AsyncSession) -> None:
    tenant = await setup_tenant(session, cap=1)
    first = await queued_template(session, tenant, await make_lead(session, tenant))
    second = await queued_template(session, tenant, await make_lead(session, tenant))
    assert (await messaging.send_message_in(session, first.id, now=MONDAY_NOON)).status == "sent"
    outcome = await messaging.send_message_in(session, second.id, now=MONDAY_NOON)
    assert (outcome.status, outcome.error) == ("blocked", "daily_cap_reached")
    # replies are not capped
    lead = await make_lead(session, tenant, status=LeadStatus.REPLIED)
    conv = Conversation(
        tenant_id=tenant.id, lead_id=lead.id, channel="whatsapp", contact_value="+201000000009"
    )
    conv.window_expires_at = MONDAY_NOON + timedelta(hours=1)
    session.add(conv)
    await session.flush()
    reply = await messaging.create_outbound(
        session,
        tenant_id=tenant.id,
        lead_id=lead.id,
        purpose=OutreachPurpose.REPLY,
        kind=MessageKind.TEXT,
        body="أكيد، دي الأسعار",
        needs_approval=False,
    )
    assert (await messaging.send_message_in(session, reply.id, now=MONDAY_NOON)).status == "sent"


async def test_quiet_hours_keep_it_queued(
    session: AsyncSession, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    tenant = await setup_tenant(session)
    message = await queued_template(session, tenant, await make_lead(session, tenant))
    enqueued.clear()
    outcome = await messaging.send_message_in(session, message.id, now=MONDAY_NIGHT)
    assert outcome.status == "queued" and outcome.retry_at is not None
    assert outcome.retry_at == datetime(2026, 11, 24, 8, 0, tzinfo=UTC)  # Tuesday 10:00 Cairo
    assert MockChannelAdapter.outbox == []
    [(name, kwargs)] = enqueued
    assert name == "job_send_message" and kwargs["_defer_until"] == outcome.retry_at


async def test_window_closed_for_free_text(session: AsyncSession) -> None:
    tenant = await setup_tenant(session)
    lead = await make_lead(session, tenant, status=LeadStatus.REPLIED)
    message = await messaging.create_outbound(
        session,
        tenant_id=tenant.id,
        lead_id=lead.id,
        purpose=OutreachPurpose.REPLY,
        kind=MessageKind.TEXT,
        body="رد",
        needs_approval=False,
    )
    outcome = await messaging.send_message_in(session, message.id, now=MONDAY_NOON)
    assert (outcome.status, outcome.error) == ("failed", "window_closed")
    assert MockChannelAdapter.outbox == []


async def test_empty_whitelist_blocks(session: AsyncSession) -> None:
    tenant = await setup_tenant(session, whitelist=[])
    message = await queued_template(session, tenant, await make_lead(session, tenant))
    outcome = await messaging.send_message_in(session, message.id, now=MONDAY_NOON)
    assert (outcome.status, outcome.error) == ("blocked", "demo_whitelist_empty")


async def test_assisted_is_never_enqueued_or_sent(
    session: AsyncSession, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    tenant = await setup_tenant(session)
    lead = await make_lead(session, tenant)
    message = await queued_template(session, tenant, lead, kind=MessageKind.ASSISTED, needs_approval=True)
    assert message.status == MessageStatus.AWAITING_MANUAL_SEND.value
    assert enqueued == []
    assert (await messaging.send_message_in(session, message.id, now=MONDAY_NOON)).status == "skipped"


async def test_queued_messages_are_enqueued(
    session: AsyncSession, enqueued: list[tuple[str, dict[str, Any]]]
) -> None:
    tenant = await setup_tenant(session)
    message = await queued_template(session, tenant, await make_lead(session, tenant))
    assert enqueued[-1][0] == "job_send_message" and enqueued[-1][1]["message_id"] == str(message.id)
    pending = await queued_template(session, tenant, await make_lead(session, tenant), needs_approval=True)
    enqueued.clear()
    await messaging.approve_message(session, tenant_id=tenant.id, message_id=pending.id, user_id=uuid.uuid4())
    assert enqueued[-1][1]["message_id"] == str(pending.id)


async def test_status_updates_never_downgrade(client: AsyncClient, session: AsyncSession) -> None:
    tenant = await setup_tenant(session)
    message = await queued_template(session, tenant, await make_lead(session, tenant))
    await messaging.send_message_in(session, message.id, now=MONDAY_NOON)
    await session.refresh(message)
    pid = str(message.provider_message_id)
    for status in ("read", "delivered", "sent", "failed"):
        await post_webhook(client, simulate_status(phone_number_id=PHONE_ID, message_id=pid, status=status))
    await session.refresh(message)
    assert message.status == MessageStatus.READ.value


async def test_failed_status_after_sent(client: AsyncClient, session: AsyncSession) -> None:
    tenant = await setup_tenant(session)
    message = await queued_template(session, tenant, await make_lead(session, tenant))
    await messaging.send_message_in(session, message.id, now=MONDAY_NOON)
    await session.refresh(message)
    payload = simulate_status(
        phone_number_id=PHONE_ID,
        message_id=str(message.provider_message_id),
        status="failed",
        error_code=131026,
    )
    await post_webhook(client, payload)
    await session.refresh(message)
    assert message.status == "failed" and message.error and message.error.startswith("undeliverable")


async def test_provider_error_is_recorded(session: AsyncSession) -> None:
    tenant = await setup_tenant(session)
    message = await queued_template(session, tenant, await make_lead(session, tenant))
    MockChannelAdapter.fail_next = "recipient_not_allowed"
    outcome = await messaging.send_message_in(session, message.id, now=MONDAY_NOON)
    assert (outcome.status, outcome.error) == ("failed", "recipient_not_allowed")


async def test_mark_sent_manually_records_the_demo_route(session: AsyncSession) -> None:
    tenant = await setup_tenant(session)
    lead = await make_lead(session, tenant)
    message = await queued_template(session, tenant, lead, kind=MessageKind.ASSISTED)
    await messaging.mark_sent_manually(
        session, tenant_id=tenant.id, message_id=message.id, user_id=uuid.uuid4()
    )
    settings = (
        await session.execute(select(BusinessSettings).where(BusinessSettings.tenant_id == tenant.id))
    ).scalar_one()
    target = messaging.resolve_demo_target(settings, lead.id)
    route = (await session.execute(select(DemoRoute).where(DemoRoute.test_phone == target))).scalar_one()
    assert route.lead_id == lead.id and message.redirected_to == target


# ================================================================================ channels API


async def test_connect_whatsapp_encrypts_and_syncs(client: AsyncClient, session: AsyncSession) -> None:
    tenant = Tenant(name="Connect")
    session.add(tenant)
    await session.flush()
    body = {"phone_number_id": "123456789", "waba_id": "987654321", "access_token": "EAAG" + "y" * 40}
    resp = await client.put("/api/v1/channels/whatsapp", json=body, headers=auth(tenant.id))
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert out["status"] == "connected" and out["display_phone_number"]
    assert "access_token" not in json.dumps(out)
    assert {t["name"] for t in out["templates"]} >= {"hello_world", "intro", "followup"}
    assert {t["name"]: t["purpose"] for t in out["templates"]}["intro"] == "intro"
    row = (
        await session.execute(select(ChannelConnection).where(ChannelConnection.tenant_id == tenant.id))
    ).scalar_one()
    assert row.secrets_encrypted and "EAAG" not in row.secrets_encrypted
    assert decrypt_json(row.secrets_encrypted)["access_token"] == body["access_token"]

    listing = (await client.get("/api/v1/channels", headers=auth(tenant.id))).json()
    assert listing["webhook_url"].endswith("/api/v1/webhooks/whatsapp")
    assert listing["items"][0]["status"] == "connected"


async def test_connect_validates_ids_and_token(client: AsyncClient, session: AsyncSession) -> None:
    tenant = Tenant(name="Validation")
    session.add(tenant)
    await session.flush()
    for body in (
        {"phone_number_id": "abc", "waba_id": "987654321", "access_token": "EAAG" + "y" * 40},
        {"phone_number_id": "123456789", "waba_id": "987654321", "access_token": "short"},
    ):
        resp = await client.put("/api/v1/channels/whatsapp", json=body, headers=auth(tenant.id))
        assert resp.status_code == 422


async def test_connect_reports_invalid_token(
    client: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = Tenant(name="Bad token")
    session.add(tenant)
    await session.flush()

    original = registry.build_channel

    def bad(channel: Any, config: dict[str, Any], secrets: dict[str, Any]) -> Any:
        return original(channel, config, {"access_token": "invalid"})

    monkeypatch.setattr(registry, "build_channel", bad)
    body = {"phone_number_id": "123456781", "waba_id": "987654321", "access_token": "EAAG" + "z" * 40}
    out = (await client.put("/api/v1/channels/whatsapp", json=body, headers=auth(tenant.id))).json()
    assert out["status"] == "error" and out["last_error"].startswith("invalid_token")


async def test_test_send_respects_demo_whitelist(client: AsyncClient, session: AsyncSession) -> None:
    tenant = await setup_tenant(session)
    bad = await client.post(
        "/api/v1/channels/whatsapp/test", json={"to": "01099999999"}, headers=auth(tenant.id)
    )
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "not_whitelisted"
    ok = await client.post(
        "/api/v1/channels/whatsapp/test", json={"to": "010 0000 0001"}, headers=auth(tenant.id)
    )
    assert ok.status_code == 200 and ok.json()["ok"] is True
    assert MockChannelAdapter.outbox[-1].to == "+201000000001"


async def test_tag_template_and_tenant_isolation(client: AsyncClient, session: AsyncSession) -> None:
    a = await setup_tenant(session, phone_id="333333333")
    b = await setup_tenant(session, phone_id="444444444")
    template = (
        (await session.execute(select(MessageTemplate).where(MessageTemplate.tenant_id == a.id)))
        .scalars()
        .first()
    )
    assert template is not None
    other = await client.put(
        f"/api/v1/channels/whatsapp/templates/{template.id}", json={"purpose": None}, headers=auth(b.id)
    )
    assert other.status_code == 404
    mine = await client.put(
        f"/api/v1/channels/whatsapp/templates/{template.id}", json={"purpose": "followup"}, headers=auth(a.id)
    )
    assert mine.status_code == 200 and mine.json()["purpose"] == "followup"
    listing_b = (await client.get("/api/v1/channels", headers=auth(b.id))).json()
    assert str(template.id) not in json.dumps(listing_b)


async def test_members_cannot_connect(client: AsyncClient, session: AsyncSession) -> None:
    tenant = await setup_tenant(session)
    body = {"phone_number_id": "123456789", "waba_id": "987654321", "access_token": "EAAG" + "y" * 40}
    resp = await client.put("/api/v1/channels/whatsapp", json=body, headers=auth(tenant.id, role="member"))
    assert resp.status_code == 403
