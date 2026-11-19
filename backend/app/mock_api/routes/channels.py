"""Mock Channels, Webhooks, Telegram & Dev Simulation routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.core.errors import AppError, NotFoundError
from app.core.security import CurrentUser
from app.mock_api.helpers import (
    classify_mock_reply,
    get_mock_current_user,
    get_tenant_settings,
    is_allowed_transition,
    is_eg_mobile,
    normalize_eg_phone,
)
from app.mock_api.routes.leads import ensure_conversation
from app.mock_api.state import (
    MockAgentRun,
    MockAgentStep,
    MockChannelConnection,
    MockLeadStatusHistory,
    MockMessage,
    MockMessageTemplate,
    MockNotification,
    get_store,
    reset_store,
)
from app.models.enums import (
    INTENT_TO_STATUS,
    AgentRunKind,
    AgentRunStatus,
    ChannelType,
    LeadStatus,
    MessageAuthor,
    MessageDirection,
    MessageKind,
    MessageStatus,
    OutreachPurpose,
    ReplyIntent,
    StepType,
)

router = APIRouter(tags=["channels-and-webhooks"])


class WhatsAppConfigIn(BaseModel):
    phone_number_id: str = Field(min_length=3)
    waba_id: str = Field(min_length=3)
    access_token: str = Field(min_length=5)


class WhatsAppTestIn(BaseModel):
    to: str = Field(min_length=6)


class SimulateInboundIn(BaseModel):
    lead_id: uuid.UUID
    text: str = Field(min_length=1, max_length=2000)
    auto_reply: bool = True


class SimulateStatusIn(BaseModel):
    message_id: uuid.UUID
    status: MessageStatus


@router.get("/channels")
async def list_channels(current_user: CurrentUser = Depends(get_mock_current_user)) -> dict[str, Any]:
    store = get_store()
    s = get_tenant_settings(store, current_user.tenant_id)
    conns = [c for c in store.channels.values() if c.tenant_id == current_user.tenant_id]
    templates = [t for t in store.templates.values() if t.tenant_id == current_user.tenant_id]
    return {
        "connections": [
            {
                "id": str(c.id),
                "channel": c.channel,
                "status": c.status,
                "config": c.config,
                "last_checked_at": c.last_checked_at,
                "last_error": c.last_error,
            }
            for c in conns
        ],
        "templates": [
            {
                "id": str(t.id),
                "name": t.name,
                "language": t.language,
                "category": t.category,
                "purpose": t.purpose,
                "body_text": t.body_text,
                "param_count": t.param_count,
                "status": t.status,
            }
            for t in templates
        ],
        "telegram": {
            "connected": bool(s.telegram_chat_id),
            "chat_id": s.telegram_chat_id,
        },
    }


@router.put("/channels/whatsapp")
async def configure_whatsapp(
    body: WhatsAppConfigIn,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> dict[str, Any]:
    store = get_store()
    now = datetime.now(UTC)
    existing = next(
        (
            c
            for c in store.channels.values()
            if c.tenant_id == current_user.tenant_id and c.channel == ChannelType.WHATSAPP.value
        ),
        None,
    )
    cfg = {
        "phone_number_id": body.phone_number_id,
        "waba_id": body.waba_id,
        "display_phone_number": "+20 100 000 0000",
    }
    if existing is None:
        existing = MockChannelConnection(
            id=uuid.uuid4(),
            tenant_id=current_user.tenant_id,
            channel=ChannelType.WHATSAPP.value,
            status="connected",
            config=cfg,
            last_checked_at=now,
        )
        store.channels[existing.id] = existing
    else:
        existing.status = "connected"
        existing.config = cfg
        existing.last_checked_at = now
        existing.last_error = None
    return {
        "id": str(existing.id),
        "channel": existing.channel,
        "status": existing.status,
        "config": existing.config,
        "last_checked_at": existing.last_checked_at,
    }


@router.post("/channels/whatsapp/test")
async def test_whatsapp_send(
    body: WhatsAppTestIn,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> dict[str, Any]:
    e164 = normalize_eg_phone(body.to)
    if not e164 or not is_eg_mobile(e164):
        raise AppError("invalid_phone", "Provide a valid Egyptian mobile number (+20...).", 422)
    return {
        "ok": True,
        "to": e164,
        "provider_message_id": f"wamid.mock.test.{uuid.uuid4().hex[:12]}",
        "note": "Simulated test message (no Meta API call made).",
    }


@router.post("/channels/whatsapp/templates/sync")
async def sync_whatsapp_templates(
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> dict[str, Any]:
    store = get_store()
    existing = [t for t in store.templates.values() if t.tenant_id == current_user.tenant_id]
    if not existing:
        t1 = MockMessageTemplate(
            id=uuid.uuid4(),
            tenant_id=current_user.tenant_id,
            channel=ChannelType.WHATSAPP.value,
            name="intro",
            language="ar",
            category="MARKETING",
            purpose="intro",
            body_text="أهلاً {{1}}! معكم {{2}} — حابين نعرض عليكم خدماتنا.",
            param_count=2,
            status="approved",
        )
        t2 = MockMessageTemplate(
            id=uuid.uuid4(),
            tenant_id=current_user.tenant_id,
            channel=ChannelType.WHATSAPP.value,
            name="followup",
            language="ar",
            category="MARKETING",
            purpose="followup",
            body_text="أهلاً {{1}}، متابعة سريعة بخصوص رسالتنا السابقة.",
            param_count=1,
            status="approved",
        )
        store.templates[t1.id] = t1
        store.templates[t2.id] = t2
        existing = [t1, t2]
    return {
        "synced": len(existing),
        "templates": [
            {
                "id": str(t.id),
                "name": t.name,
                "language": t.language,
                "category": t.category,
                "purpose": t.purpose,
                "body_text": t.body_text,
                "param_count": t.param_count,
                "status": t.status,
            }
            for t in existing
        ],
    }


@router.get("/webhooks/whatsapp", response_class=PlainTextResponse)
async def verify_whatsapp_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
) -> str:
    if hub_mode != "subscribe":
        raise AppError("invalid_mode", "Invalid hub.mode", 400)
    return hub_challenge


@router.post("/webhooks/whatsapp")
async def receive_whatsapp_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "received", "mock": True, "entries": len(payload.get("entry", []))}


@router.post("/channels/telegram/link")
async def create_telegram_link(current_user: CurrentUser = Depends(get_mock_current_user)) -> dict[str, str]:
    store = get_store()
    s = get_tenant_settings(store, current_user.tenant_id)
    code = uuid.uuid4().hex[:10]
    s.telegram_link_code = code
    return {"deep_link": f"https://t.me/NexusB2BMockBot?start={code}", "code": code}


@router.post("/webhooks/telegram")
async def telegram_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    store = get_store()
    msg = payload.get("message") or {}
    text = str(msg.get("text") or "")
    chat_id = str((msg.get("chat") or {}).get("id") or "mock-chat-1")
    if text.startswith("/start "):
        code = text.split(" ", 1)[1].strip()
        for s in store.settings.values():
            if s.telegram_link_code == code:
                s.telegram_chat_id = chat_id
                s.telegram_link_code = None
                return {"ok": True, "linked": True, "company_name": s.company_name}
    return {"ok": True, "linked": False}


@router.post("/mock/simulate-inbound", tags=["mock-dev"])
async def simulate_inbound_reply(
    body: SimulateInboundIn,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> dict[str, Any]:
    """Dev-only: simulate an inbound WhatsApp message & AI Reply Agent classification."""
    store = get_store()
    lead = store.leads.get(body.lead_id)
    if lead is None or lead.tenant_id != current_user.tenant_id:
        raise NotFoundError("lead")

    now = datetime.now(UTC)
    conv = ensure_conversation(store, current_user.tenant_id, lead, "+201000009901")
    conv.window_expires_at = now + timedelta(hours=24)

    intent, suggested_reply, should_escalate = classify_mock_reply(body.text)

    inbound_msg = MockMessage(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        conversation_id=conv.id,
        lead_id=lead.id,
        direction=MessageDirection.INBOUND.value,
        channel=ChannelType.WHATSAPP.value,
        author=MessageAuthor.LEAD.value,
        kind=MessageKind.TEXT.value,
        body=body.text.strip(),
        status=MessageStatus.RECEIVED.value,
        provider_message_id=f"wamid.mock.in.{uuid.uuid4().hex[:10]}",
        reply_intent=intent.value,
        sent_at=now,
        created_at=now,
    )
    store.messages[inbound_msg.id] = inbound_msg
    lead.last_inbound_at = now

    target_status = INTENT_TO_STATUS[intent]
    if is_allowed_transition(LeadStatus(lead.status), target_status, force=True):
        h_id = uuid.uuid4()
        store.status_history[h_id] = MockLeadStatusHistory(
            id=h_id,
            tenant_id=current_user.tenant_id,
            lead_id=lead.id,
            from_status=lead.status,
            to_status=target_status.value,
            reason=f"Reply Agent classified intent: {intent.value}",
            actor="agent",
            created_at=now,
        )
        lead.status = target_status.value

    if intent == ReplyIntent.OPTED_OUT:
        lead.agent_paused = True

    # Trace reply agent run
    run_id = uuid.uuid4()
    run = MockAgentRun(
        id=run_id,
        tenant_id=current_user.tenant_id,
        kind=AgentRunKind.REPLY.value,
        status=AgentRunStatus.SUCCEEDED.value,
        trigger="webhook",
        input={"lead_id": str(lead.id), "text": body.text[:80]},
        output_summary={"intent": intent.value, "escalated": should_escalate},
        created_at=now,
        started_at=now,
        finished_at=now + timedelta(seconds=2),
        total_input_tokens=840,
        total_output_tokens=210,
        total_cost_usd=0.0016,
    )
    store.runs[run_id] = run
    s1 = uuid.uuid4()
    store.steps[s1] = MockAgentStep(
        id=s1,
        tenant_id=current_user.tenant_id,
        run_id=run_id,
        seq=1,
        step_type=StepType.LLM_CALL.value,
        name="reply_classifier",
        input={"text": body.text},
        output={"intent": intent.value, "confidence": 0.94},
        model="gemini-3.5-flash-lite",
        input_tokens=400,
        output_tokens=70,
        cost_usd=0.0004,
        latency_ms=320,
        lead_id=lead.id,
        created_at=now,
    )

    outbound_msg: MockMessage | None = None
    if body.auto_reply and intent != ReplyIntent.OPTED_OUT:
        outbound_msg = MockMessage(
            id=uuid.uuid4(),
            tenant_id=current_user.tenant_id,
            conversation_id=conv.id,
            lead_id=lead.id,
            direction=MessageDirection.OUTBOUND.value,
            channel=ChannelType.WHATSAPP.value,
            author=MessageAuthor.AGENT.value,
            kind=MessageKind.TEXT.value,
            purpose=OutreachPurpose.REPLY.value,
            body=suggested_reply,
            status=MessageStatus.SENT.value,
            provider_message_id=f"wamid.mock.reply.{uuid.uuid4().hex[:10]}",
            sent_at=now + timedelta(seconds=1),
            agent_run_id=run_id,
            created_at=now + timedelta(seconds=1),
        )
        store.messages[outbound_msg.id] = outbound_msg
        lead.last_outbound_at = now + timedelta(seconds=1)

    if should_escalate:
        lead.agent_paused = True
        notif_kind = {
            ReplyIntent.WANTS_MANAGEMENT: "wants_management",
            ReplyIntent.WANTS_OFFER: "wants_offer",
        }.get(intent, "hot_lead")
        notif = MockNotification(
            id=uuid.uuid4(),
            tenant_id=current_user.tenant_id,
            lead_id=lead.id,
            kind=notif_kind,
            title=f"تصعيد من {lead.name}",
            body=f"رد العميل: {body.text[:120]}",
            created_at=now,
        )
        store.notifications[notif.id] = notif

    return {
        "inbound_message_id": str(inbound_msg.id),
        "intent": intent.value,
        "lead_status": lead.status,
        "escalated": should_escalate,
        "suggested_reply": suggested_reply,
        "reply_message_id": str(outbound_msg.id) if outbound_msg else None,
        "run_id": str(run_id),
    }


@router.post("/mock/simulate-status", tags=["mock-dev"])
async def simulate_message_status(
    body: SimulateStatusIn,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> dict[str, Any]:
    store = get_store()
    msg = store.messages.get(body.message_id)
    if msg is None or msg.tenant_id != current_user.tenant_id:
        raise NotFoundError("message")
    msg.status = body.status.value
    return {"id": str(msg.id), "status": msg.status}


@router.post("/mock/reset", tags=["mock-dev"])
async def reset_mock_data() -> dict[str, Any]:
    """Dev-only: reset all in-memory mock data back to the initial deterministic seed."""
    store = reset_store()
    return {
        "reset": True,
        "tenants": len(store.tenants),
        "leads": len(store.leads),
        "runs": len(store.runs),
    }
