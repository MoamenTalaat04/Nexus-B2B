"""Messaging service (CONTRACTS section 9, P3-2): create, approve, send and receive WhatsApp messages.

Outbound life cycle
  create_outbound → pending_approval  (needs_approval)     → approve_message → queued → job_send_message
                  → queued            (no approval needed) → job_send_message
                  → awaiting_manual_send (kind=ASSISTED: the owner sends it from their phone; never enqueued)
                  → blocked           (the lead opted out)
  send_message (the job body) re-checks every guardrail at send time:
    opted_out → blocked · agent paused (agent message nobody approved) → blocked ·
    daily_send_cap reached (first touches/follow-ups only) → blocked ·
    outside quiet hours / not a working day (first touches/follow-ups only) → stays queued, retried at the
    next allowed time · demo_mode → the whitelisted test phone (resolve_demo_target, CONTRACTS section 12);
    empty whitelist → blocked "demo_whitelist_empty" · TEXT outside the 24h window → failed "window_closed".
  On success: sent + provider_message_id, lead.first_contacted_at/last_outbound_at, the conversation, then
  outreach.on_message_sent(session, message) (QUEUED/LATER → CONTACTED). One EXTERNAL_API trace step per
  attempt (no body, phone masked).

Inbound (webhook → handle_inbound): find the lead (demo route → contact → "#REFCODE"), save the message, open
the 24h window, STOP words → OPTED_OUT first, else → REPLIED when allowed; the caller enqueues
job_handle_inbound. Status webhooks → apply_status (never downgrades read → delivered).
"""

import hashlib
import logging
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import registry
from app.adapters.base import InboundMessage, SendResult, StatusUpdate
from app.config import settings as app_settings
from app.core import lead_state
from app.core.errors import AppError, NotFoundError
from app.core.geo_eg_coords import normalize_arabic
from app.core.phones import normalize_eg_phone
from app.core.tracing import RunContext, agent_run, mask_phones
from app.models.enums import (
    AgentRunKind,
    ChannelType,
    ContactType,
    LeadStatus,
    MessageAuthor,
    MessageDirection,
    MessageKind,
    MessageStatus,
    OutreachPurpose,
    StepType,
)
from app.models.leads import Contact, Lead
from app.models.messaging import ChannelConnection, Conversation, DemoRoute, Message, MessageTemplate
from app.models.notifications import Notification
from app.models.runs import AgentStep
from app.models.tenants import BusinessSettings
from app.services.notifications import notify_owner
from app.workers.queue import enqueue

logger = logging.getLogger("app.services.messaging")

ASSISTANT_PREFILL_AR = "أهلاً، حابب أعرف أكتر عن منتجاتكم"
WINDOW = timedelta(hours=24)
SEND_DELAY = timedelta(seconds=3)  # lets the caller commit before the worker reads the message
CAPPED_PURPOSES = (OutreachPurpose.FIRST_TOUCH.value, OutreachPurpose.FOLLOWUP.value)
SENDABLE = (MessageStatus.QUEUED.value, MessageStatus.APPROVED.value)
OPEN_OUTBOUND = (
    MessageStatus.PENDING_APPROVAL.value,
    MessageStatus.APPROVED.value,
    MessageStatus.QUEUED.value,
    MessageStatus.AWAITING_MANUAL_SEND.value,
)
SENT_STATUSES = (MessageStatus.SENT.value, MessageStatus.DELIVERED.value, MessageStatus.READ.value)
STATUS_RANK = {
    MessageStatus.QUEUED.value: 0,
    MessageStatus.APPROVED.value: 0,
    MessageStatus.SENT.value: 1,
    MessageStatus.DELIVERED.value: 2,
    MessageStatus.READ.value: 3,
}
REF_CODE_RE = re.compile(r"#\s?([A-Za-z2-9]{6})\b")

# Opt-out words. A message that IS one of these (after normalization) opts out; so does a short message (≤ 4
# words) containing a single word, or any message containing a phrase. Normalized like normalize_arabic
# (أ/إ/آ→ا, ة→ه, ى→ي, lowercase). Kept in one place so the team can extend it.
STOP_WORDS = frozenset(
    {
        "stop",
        "unsubscribe",
        "cancel",
        "الغاء",
        "الغي",
        "وقف",
        "اوقف",
        "بطل",
        "بطلوا",
        "كفايه",
        "ستوب",
    }
)
STOP_PHRASES = (
    "stop sending",
    "stop messaging",
    "dont message",
    "don't message",
    "remove my number",
    "مش عايز رسايل",
    "مش عايزه رسايل",
    "مش عاوز رسايل",
    "مش عايز رسائل",
    "متبعتليش",
    "ماتبعتليش",
    "متبعتوليش",
    "ماتبعتوليش",
    "متبعتوش",
    "بطلوا تبعتوا",
    "بطل تبعت",
    "متكلمنيش تاني",
    "متراسلنيش",
    "لا تراسلني",
    "امسح رقمي",
    "امسحوا رقمي",
    "شيل رقمي",
    "شيلوا رقمي",
    "الغي الاشتراك",
    "الغاء الاشتراك",
)
_NON_WORD_RE = re.compile(r"[^\w\s']", re.UNICODE)


def is_stop_message(text: str) -> bool:
    norm = " ".join(_NON_WORD_RE.sub(" ", normalize_arabic(text or "")).split())
    if not norm:
        return False
    if norm in STOP_WORDS or any(phrase in norm for phrase in STOP_PHRASES):
        return True
    words = norm.split()
    return len(words) <= 4 and any(w in STOP_WORDS for w in words)


def local_tz() -> ZoneInfo:
    return ZoneInfo(app_settings.TIMEZONE)


def mask(phone: str | None) -> str | None:
    return mask_phones(phone) if phone else None


# ---------------------------------------------------------------------------------------------- helpers


def render_template(body_text: str, params: list[str]) -> str:
    """Replace {{1}}, {{2}} … with the params (for previews; WhatsApp renders the real message)."""
    text = body_text
    for i, value in enumerate(params, 1):
        text = text.replace(f"{{{{{i}}}}}", value)
    return text


async def primary_mobile(session: AsyncSession, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> str | None:
    row = await session.execute(
        select(Contact.value)
        .where(
            Contact.tenant_id == tenant_id,
            Contact.lead_id == lead_id,
            Contact.type == ContactType.MOBILE.value,
        )
        .order_by(Contact.is_primary.desc(), Contact.confidence.desc(), Contact.created_at)
        .limit(1)
    )
    return row.scalar_one_or_none()


async def get_whatsapp_connection(session: AsyncSession, tenant_id: uuid.UUID) -> ChannelConnection | None:
    return (
        await session.execute(
            select(ChannelConnection).where(
                ChannelConnection.tenant_id == tenant_id,
                ChannelConnection.channel == ChannelType.WHATSAPP.value,
            )
        )
    ).scalar_one_or_none()


async def _conversation(session: AsyncSession, lead: Lead, contact_value: str | None = None) -> Conversation:
    conv = (
        await session.execute(
            select(Conversation).where(
                Conversation.tenant_id == lead.tenant_id,
                Conversation.lead_id == lead.id,
                Conversation.channel == ChannelType.WHATSAPP.value,
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        conv = Conversation(
            tenant_id=lead.tenant_id,
            lead_id=lead.id,
            channel=ChannelType.WHATSAPP.value,
            contact_value=contact_value or await primary_mobile(session, lead.tenant_id, lead.id) or "",
        )
        session.add(conv)
        await session.flush()
    elif contact_value and not conv.contact_value:
        conv.contact_value = contact_value
    return conv


async def enqueue_send(message_id: uuid.UUID, *, defer_until: datetime | None = None) -> None:
    """Enqueue job_send_message; a queue outage is logged, and job_requeue_stuck_messages retries later."""
    try:
        if defer_until is not None:
            await enqueue(
                "job_send_message",
                message_id=str(message_id),
                _defer_until=defer_until,
                _job_id=f"send:{message_id}:{int(defer_until.timestamp())}",
            )
        else:
            await enqueue("job_send_message", message_id=str(message_id), _defer_by=SEND_DELAY)
    except Exception:
        logger.exception("could not enqueue job_send_message for %s (the sweeper will retry)", message_id)


# ---------------------------------------------------------------------------------------------- outbound API


async def create_outbound(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    lead_id: uuid.UUID,
    purpose: OutreachPurpose,
    kind: MessageKind,
    body: str,
    template_name: str | None = None,
    template_params: list[str] | None = None,
    author: MessageAuthor = MessageAuthor.AGENT,
    needs_approval: bool,
    agent_run_id: uuid.UUID | None = None,
) -> Message:
    lead = (
        await session.execute(select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if lead is None:
        raise NotFoundError("lead")
    conv = await _conversation(session, lead)
    error = None
    if lead.status == LeadStatus.OPTED_OUT.value:
        status, error = MessageStatus.BLOCKED, "opted_out"
    elif kind == MessageKind.ASSISTED:
        status = MessageStatus.AWAITING_MANUAL_SEND  # the owner sends it; never enqueued
    elif needs_approval:
        status = MessageStatus.PENDING_APPROVAL
    else:
        status = MessageStatus.QUEUED
    message = Message(
        tenant_id=tenant_id,
        conversation_id=conv.id,
        lead_id=lead_id,
        direction=MessageDirection.OUTBOUND.value,
        channel=ChannelType.WHATSAPP.value,
        author=MessageAuthor(author).value,
        kind=MessageKind(kind).value,
        purpose=OutreachPurpose(purpose).value,
        template_name=template_name,
        template_params=template_params,
        body=body,
        status=status.value,
        error=error,
        agent_run_id=agent_run_id,
    )
    session.add(message)
    await session.flush()
    if status == MessageStatus.QUEUED:
        await enqueue_send(message.id)
    return message


async def _message(session: AsyncSession, tenant_id: uuid.UUID, message_id: uuid.UUID) -> Message:
    message = (
        await session.execute(
            select(Message).where(Message.id == message_id, Message.tenant_id == tenant_id).with_for_update()
        )
    ).scalar_one_or_none()
    if message is None:
        raise NotFoundError("message")
    return message


def _require(message: Message, *allowed: MessageStatus) -> None:
    if message.status not in {s.value for s in allowed}:
        raise AppError(
            "invalid_message_status",
            f"This message is {message.status.replace('_', ' ')} and cannot be changed this way.",
            status_code=409,
        )


async def approve_message(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    edited_params: list[str] | None = None,
    edited_body: str | None = None,
) -> Message:
    message = await _message(session, tenant_id, message_id)
    _require(message, MessageStatus.PENDING_APPROVAL)
    lead = await session.get(Lead, message.lead_id)
    if lead is not None and lead.status == LeadStatus.OPTED_OUT.value:
        message.status, message.error = MessageStatus.BLOCKED.value, "opted_out"
        await session.flush()
        return message
    if edited_params is not None:
        message.template_params = edited_params
        template = (
            await session.execute(
                select(MessageTemplate).where(
                    MessageTemplate.tenant_id == tenant_id, MessageTemplate.name == message.template_name
                )
            )
        ).scalar_one_or_none()
        if template is not None:
            message.body = render_template(template.body_text, edited_params)
    if edited_body is not None:
        message.body = edited_body
    message.approved_by_user_id = user_id
    message.status = MessageStatus.QUEUED.value
    await session.flush()
    await enqueue_send(message.id)
    return message


async def reject_message(
    session: AsyncSession, *, tenant_id: uuid.UUID, message_id: uuid.UUID, user_id: uuid.UUID
) -> Message:
    message = await _message(session, tenant_id, message_id)
    _require(message, MessageStatus.PENDING_APPROVAL, MessageStatus.AWAITING_MANUAL_SEND)
    message.status = MessageStatus.REJECTED.value
    await session.flush()
    return message


async def mark_sent_manually(
    session: AsyncSession, *, tenant_id: uuid.UUID, message_id: uuid.UUID, user_id: uuid.UUID
) -> Message:
    """Assisted only: awaiting_manual_send → sent, then outreach.on_message_sent()."""
    message = await _message(session, tenant_id, message_id)
    _require(message, MessageStatus.AWAITING_MANUAL_SEND)
    now = datetime.now(UTC)
    message.status = MessageStatus.SENT.value
    message.sent_at = now
    message.author = MessageAuthor.HUMAN.value
    message.approved_by_user_id = user_id
    lead = await session.get(Lead, message.lead_id)
    if lead is not None:
        lead.first_contacted_at = lead.first_contacted_at or now
        lead.last_outbound_at = now
        settings = await _settings(session, tenant_id)
        if settings is not None and settings.demo_mode:
            # The wa.me link opened the stable demo phone for this lead; record the route so an inbound from
            # that phone (through our Cloud API number) maps back to the lead.
            target = resolve_demo_target(settings, lead.id)
            if target:
                await _upsert_route(session, tenant_id, target, lead.id)
                message.redirected_to = target
    await session.flush()
    from app.services import outreach  # local import: outreach imports this module

    await outreach.on_message_sent(session, message)
    return message


def build_wa_link(phone_e164: str, text: str) -> str:
    """https://wa.me/<digits>?text=<url-encoded text>. The caller passes the demo target in demo mode."""
    digits = "".join(ch for ch in phone_e164 if ch.isdigit())
    return f"https://wa.me/{digits}?text={quote(text)}"


def assistant_link(settings: BusinessSettings, connection: Any, lead: Lead) -> str | None:
    """wa.me link to the tenant's own Cloud API number, pre-filled with "#<ref_code>" (None if none)."""
    if connection is None or getattr(connection, "status", None) != "connected":
        return None
    config: dict[str, Any] = getattr(connection, "config", None) or {}
    number = config.get("display_phone_number")
    if not number:
        return None
    return build_wa_link(str(number), f"{ASSISTANT_PREFILL_AR} #{lead.ref_code}")


# ---------------------------------------------------------------------------------------------- demo routing


def _whitelist(settings: BusinessSettings) -> list[str]:
    out: list[str] = []
    for raw in settings.demo_whitelist or []:
        phone = normalize_eg_phone(str(raw)) or str(raw)
        if phone not in out:
            out.append(phone)
    return out


def resolve_demo_target(
    settings: BusinessSettings, lead_id: uuid.UUID, routes: Sequence[DemoRoute] | None = None
) -> str | None:
    """The whitelisted test phone for this lead (CONTRACTS section 12), or None if the whitelist is empty.

    With `routes` (the tenant's demo_routes): the phone already routed to this lead, else a phone never used,
    else the one unused for longest. Without routes: a stable phone per lead (used for wa.me links).
    route_demo() is the async version that also writes demo_routes.
    """
    whitelist = _whitelist(settings)
    if not whitelist:
        return None
    if routes is None:
        index = int(hashlib.sha256(str(lead_id).encode()).hexdigest(), 16) % len(whitelist)
        return whitelist[index]
    by_phone = {r.test_phone: r for r in routes if r.test_phone in whitelist}
    for phone, route in by_phone.items():
        if route.lead_id == lead_id:
            return phone
    unused = [p for p in whitelist if p not in by_phone]
    if unused:
        return unused[0]
    return min(by_phone.values(), key=lambda r: r.updated_at).test_phone


async def _upsert_route(session: AsyncSession, tenant_id: uuid.UUID, phone: str, lead_id: uuid.UUID) -> None:
    route = (
        await session.execute(
            select(DemoRoute).where(DemoRoute.tenant_id == tenant_id, DemoRoute.test_phone == phone)
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if route is None:
        session.add(DemoRoute(tenant_id=tenant_id, test_phone=phone, lead_id=lead_id, updated_at=now))
    else:
        route.lead_id = lead_id
        route.updated_at = now  # "last used"
    await session.flush()


async def route_demo(session: AsyncSession, settings: BusinessSettings, lead_id: uuid.UUID) -> str | None:
    """resolve_demo_target with the tenant's routes, then upsert demo_routes(test_phone → lead_id)."""
    routes = list(
        (await session.execute(select(DemoRoute).where(DemoRoute.tenant_id == settings.tenant_id))).scalars()
    )
    phone = resolve_demo_target(settings, lead_id, routes)
    if phone is not None:
        await _upsert_route(session, settings.tenant_id, phone, lead_id)
    return phone


# ---------------------------------------------------------------------------------------------- sending rules


def in_send_window(settings: BusinessSettings, now: datetime) -> bool:
    local = now.astimezone(local_tz())
    if local.weekday() not in (settings.working_days or []):
        return False
    return settings.quiet_hours_start <= local.time().replace(tzinfo=None) < settings.quiet_hours_end


def next_send_time(settings: BusinessSettings, now: datetime) -> datetime:
    """The next moment inside the sending window (working day, quiet_hours_start..end, Cairo)."""
    if in_send_window(settings, now):
        return now
    local = now.astimezone(local_tz())
    for day in range(0, 8):
        candidate = (local + timedelta(days=day)).replace(
            hour=settings.quiet_hours_start.hour,
            minute=settings.quiet_hours_start.minute,
            second=0,
            microsecond=0,
        )
        if candidate > local and candidate.weekday() in (settings.working_days or []):
            return candidate.astimezone(UTC)
    return now + timedelta(days=1)  # no working days configured: try again tomorrow


def start_of_local_day(now: datetime) -> datetime:
    local = now.astimezone(local_tz())
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


async def sent_today(session: AsyncSession, tenant_id: uuid.UUID, now: datetime) -> int:
    """First touches + follow-ups the API actually sent today (Cairo day); replies are not capped."""
    total = await session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.tenant_id == tenant_id,
            Message.direction == MessageDirection.OUTBOUND.value,
            Message.purpose.in_(CAPPED_PURPOSES),
            Message.status.in_(SENT_STATUSES),
            Message.sent_at >= start_of_local_day(now),
        )
    )
    return int(total or 0)


async def _settings(session: AsyncSession, tenant_id: uuid.UUID) -> BusinessSettings | None:
    return (
        await session.execute(select(BusinessSettings).where(BusinessSettings.tenant_id == tenant_id))
    ).scalar_one_or_none()


async def _notify_channel_error_once(
    session: AsyncSession, tenant_id: uuid.UUID, title: str, body: str
) -> None:
    exists = await session.scalar(
        select(Notification.id)
        .where(
            Notification.tenant_id == tenant_id,
            Notification.kind == "channel_error",
            Notification.title == title,
            Notification.read_at.is_(None),
        )
        .limit(1)
    )
    if exists is None:
        await notify_owner(session, tenant_id=tenant_id, kind="channel_error", title=title, body=body)


async def _trace_context(message: Message) -> RunContext | None:
    """The RunContext of the run that created the message, continuing its step numbering (or None)."""
    if message.agent_run_id is None:
        return None
    from app.core.tracing import _trace_session  # the same session factory the tracer uses

    async with _trace_session() as trace_session:
        last = await trace_session.scalar(
            select(func.coalesce(func.max(AgentStep.seq), 0)).where(AgentStep.run_id == message.agent_run_id)
        )
    kind = (
        AgentRunKind.REPLY if message.purpose == OutreachPurpose.REPLY.value else AgentRunKind.OUTREACH_TICK
    )
    ctx = RunContext(message.agent_run_id, message.tenant_id, kind)
    ctx._seq = int(last or 0)
    return ctx


# ---------------------------------------------------------------------------------------------- send


@dataclass
class SendOutcome:
    status: str  # the message's status afterwards, or "not_found" / "skipped"
    error: str | None = None
    retry_at: datetime | None = None


async def send_message(message_id: uuid.UUID) -> None:
    """Job body (job_send_message): send one queued message, with every guardrail checked again."""
    from app.db import SessionLocal

    async with SessionLocal() as session:
        await send_message_in(session, message_id)


async def send_message_in(
    session: AsyncSession, message_id: uuid.UUID, *, now: datetime | None = None
) -> SendOutcome:
    """send_message on a given session (tests, the job). Commits."""
    now = now or datetime.now(UTC)
    message = (
        await session.execute(select(Message).where(Message.id == message_id).with_for_update())
    ).scalar_one_or_none()
    if message is None:
        return SendOutcome("not_found")
    if message.direction != MessageDirection.OUTBOUND.value or message.status not in SENDABLE:
        return SendOutcome("skipped")  # already handled (idempotent)
    if message.kind == MessageKind.ASSISTED.value:
        return SendOutcome("skipped")  # the owner sends these
    lead = await session.get(Lead, message.lead_id)
    settings = await _settings(session, message.tenant_id)
    if lead is None or settings is None or lead.tenant_id != message.tenant_id:
        return await _finish(session, message, MessageStatus.FAILED, "lead_not_found")

    if lead.status == LeadStatus.OPTED_OUT.value:
        return await _finish(session, message, MessageStatus.BLOCKED, "opted_out")
    if (
        lead.agent_paused
        and message.author == MessageAuthor.AGENT.value
        and message.approved_by_user_id is None
    ):
        return await _finish(session, message, MessageStatus.BLOCKED, "agent_paused")
    capped = message.purpose in CAPPED_PURPOSES
    if capped and await sent_today(session, message.tenant_id, now) >= settings.daily_send_cap:
        return await _finish(session, message, MessageStatus.BLOCKED, "daily_cap_reached")
    if capped and not in_send_window(settings, now):
        # Stay queued and retry at the next allowed time. lead.next_action_at is left alone on purpose: the
        # outreach engine (P3-3) uses it for the sequence schedule (e.g. the follow-up in 3 days).
        retry_at = next_send_time(settings, now)
        message.error = "outside_quiet_hours"
        await session.commit()
        await enqueue_send(message.id, defer_until=retry_at)
        return SendOutcome(MessageStatus.QUEUED.value, "outside_quiet_hours", retry_at)

    if settings.demo_mode:
        target = await route_demo(session, settings, lead.id)
        if target is None:
            return await _finish(session, message, MessageStatus.BLOCKED, "demo_whitelist_empty")
        message.redirected_to = target
    else:
        target = await primary_mobile(session, lead.tenant_id, lead.id)
        if target is None:
            return await _finish(session, message, MessageStatus.FAILED, "no_mobile")

    conv = await _conversation(session, lead)
    if message.conversation_id is None:
        message.conversation_id = conv.id
    if message.kind == MessageKind.TEXT.value and not (
        conv.window_expires_at is not None and conv.window_expires_at > now
    ):
        return await _finish(session, message, MessageStatus.FAILED, "window_closed")

    try:
        adapter = await registry.get_channel(session, message.tenant_id, ChannelType.WHATSAPP)
    except registry.ChannelNotConnected:
        await _notify_channel_error_once(
            session,
            message.tenant_id,
            "WhatsApp is not connected",
            "Messages are waiting to be sent. Connect WhatsApp in Settings → Channels.",
        )
        return await _finish(session, message, MessageStatus.FAILED, "channel_not_connected")

    started = datetime.now(UTC)
    if message.kind == MessageKind.TEMPLATE.value:
        template = (
            await session.execute(
                select(MessageTemplate).where(
                    MessageTemplate.tenant_id == message.tenant_id,
                    MessageTemplate.name == message.template_name,
                )
            )
        ).scalar_one_or_none()
        language = template.language if template else "ar"
        result = await adapter.send_template(
            to=target,
            template_name=message.template_name or "",
            language=language,
            params=list(message.template_params or []),
        )
    else:
        result = await adapter.send_text(to=target, body=message.body)
    latency = int((datetime.now(UTC) - started).total_seconds() * 1000)
    await _trace_send(message, result, target, latency)

    if not result.ok:
        error = result.error or "provider_error"
        if error.startswith("invalid_token"):
            connection = await get_whatsapp_connection(session, message.tenant_id)
            if connection is not None:
                connection.status, connection.last_error = "error", error
            await _notify_channel_error_once(
                session,
                message.tenant_id,
                "WhatsApp token expired or invalid",
                "Sending stopped: reconnect WhatsApp in Settings → Channels with a new access token.",
            )
        return await _finish(session, message, MessageStatus.FAILED, error)

    message.status = MessageStatus.SENT.value
    message.provider_message_id = result.provider_message_id
    message.sent_at = now
    message.error = None
    lead.last_outbound_at = now
    lead.first_contacted_at = lead.first_contacted_at or now
    await session.flush()
    from app.services import outreach  # local import: outreach imports this module

    await outreach.on_message_sent(session, message)
    await session.commit()
    return SendOutcome(MessageStatus.SENT.value)


async def _finish(session: AsyncSession, message: Message, status: MessageStatus, error: str) -> SendOutcome:
    message.status = status.value
    message.error = error
    await session.commit()
    logger.info("message %s %s: %s", message.id, status.value, error)
    return SendOutcome(status.value, error)


async def _trace_send(message: Message, result: SendResult, target: str, latency_ms: int) -> None:
    payload_in = {
        "message_id": str(message.id),
        "kind": message.kind,
        "purpose": message.purpose,
        "template": message.template_name,
        "to": mask(target),
        "demo_redirect": message.redirected_to is not None,
    }
    payload_out = {"ok": result.ok, "provider_message_id": result.provider_message_id, "error": result.error}
    try:
        ctx = await _trace_context(message)
        if ctx is not None:
            await ctx.step(
                StepType.EXTERNAL_API,
                "whatsapp.send",
                input=payload_in,
                output=payload_out,
                latency_ms=latency_ms,
                lead_id=message.lead_id,
            )
            return
        # A message no agent run created (e.g. a manual text): its own short run so the send is traced.
        async with agent_run(
            message.tenant_id,
            AgentRunKind.OUTREACH_TICK,
            trigger="manual",
            input={"message_id": str(message.id)},
        ) as run:
            await run.step(
                StepType.EXTERNAL_API,
                "whatsapp.send",
                input=payload_in,
                output=payload_out,
                latency_ms=latency_ms,
                lead_id=message.lead_id,
            )
            run.output_summary = {"sent": result.ok}
    except Exception:  # tracing must never block a send that already happened
        logger.exception("could not trace the send of message %s", message.id)


# ---------------------------------------------------------------------------------------------- inbound


async def connection_for_account(session: AsyncSession, phone_number_id: str) -> ChannelConnection | None:
    """The tenant's WhatsApp connection that owns this Meta phone_number_id (webhook routing)."""
    if not phone_number_id:
        return None
    return (
        await session.execute(
            select(ChannelConnection).where(
                ChannelConnection.channel == ChannelType.WHATSAPP.value,
                ChannelConnection.config["phone_number_id"].astext == phone_number_id,
            )
        )
    ).scalar_one_or_none()


@dataclass
class InboundOutcome:
    message: Message | None
    duplicate: bool = False
    opted_out: bool = False
    reason: str | None = None  # why nothing was stored: unknown_sender, unknown_account
    matched_by: str | None = None  # demo_route | contact | ref_code


async def _find_lead(
    session: AsyncSession, settings: BusinessSettings, phone: str, text: str
) -> tuple[Lead | None, str]:
    tenant_id = settings.tenant_id
    whitelisted = settings.demo_mode and phone in _whitelist(settings)
    if whitelisted:
        route = (
            await session.execute(
                select(DemoRoute).where(DemoRoute.tenant_id == tenant_id, DemoRoute.test_phone == phone)
            )
        ).scalar_one_or_none()
        if route is not None:
            lead = await session.get(Lead, route.lead_id)
            if lead is not None:
                return lead, "demo_route"
    else:
        lead_id = await session.scalar(
            select(Contact.lead_id)
            .where(
                Contact.tenant_id == tenant_id,
                Contact.value == phone,
                Contact.type.in_([ContactType.MOBILE.value, ContactType.WHATSAPP_LINK.value]),
            )
            .order_by(Contact.created_at.desc())
            .limit(1)
        )
        if lead_id is not None:
            lead = await session.get(Lead, lead_id)
            if lead is not None:
                return lead, "contact"
    for code in REF_CODE_RE.findall(text or ""):
        lead = (
            await session.execute(
                select(Lead).where(Lead.tenant_id == tenant_id, Lead.ref_code == code.upper())
            )
        ).scalar_one_or_none()
        if lead is None:
            continue
        if whitelisted:
            await _upsert_route(session, tenant_id, phone, lead.id)  # a tester started the chat
        else:
            session.add(
                Contact(
                    tenant_id=tenant_id,
                    lead_id=lead.id,
                    type=ContactType.MOBILE.value,
                    value=phone,
                    source="lead_initiated",
                    is_primary=False,
                    confidence=1.0,
                )
            )
            await session.flush()
        return lead, "ref_code"
    return None, "unknown"


async def handle_inbound(session: AsyncSession, inbound: InboundMessage) -> InboundOutcome:
    """Store one inbound WhatsApp message (idempotent on provider_message_id). Flushes; the caller commits and
    then enqueues job_handle_inbound(message_id) when a new message was stored."""
    existing = (
        await session.execute(
            select(Message).where(Message.provider_message_id == inbound.provider_message_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return InboundOutcome(existing, duplicate=True)
    connection = await connection_for_account(session, inbound.account_ref)
    if connection is None:
        logger.warning("whatsapp inbound for an unknown phone_number_id; ignored")
        return InboundOutcome(None, reason="unknown_account")
    tenant_id = connection.tenant_id
    settings = await _settings(session, tenant_id)
    if settings is None:
        return InboundOutcome(None, reason="unknown_account")
    phone = normalize_eg_phone(inbound.from_phone) or inbound.from_phone
    lead, how = await _find_lead(session, settings, phone, inbound.text)
    if lead is None:
        await notify_owner(
            session,
            tenant_id=tenant_id,
            kind="channel_error",
            title="Message from an unknown number",
            body=f"{phone}: {inbound.text[:300]}",
        )
        return InboundOutcome(None, reason="unknown_sender")

    conv = await _conversation(session, lead, contact_value=phone)
    message = Message(
        tenant_id=tenant_id,
        conversation_id=conv.id,
        lead_id=lead.id,
        direction=MessageDirection.INBOUND.value,
        channel=ChannelType.WHATSAPP.value,
        author=MessageAuthor.LEAD.value,
        kind=MessageKind.TEXT.value,
        body=inbound.text,
        status=MessageStatus.RECEIVED.value,
        provider_message_id=inbound.provider_message_id,
        sent_at=inbound.timestamp,
        redirected_to=phone if settings.demo_mode and phone in _whitelist(settings) else None,
    )
    session.add(message)
    expires = inbound.timestamp + WINDOW
    if conv.window_expires_at is None or conv.window_expires_at < expires:
        conv.window_expires_at = expires
    if lead.last_inbound_at is None or lead.last_inbound_at < inbound.timestamp:
        lead.last_inbound_at = inbound.timestamp
    await session.flush()

    current = LeadStatus(lead.status)
    if is_stop_message(inbound.text):
        if lead_state.is_allowed(current, LeadStatus.OPTED_OUT):
            await lead_state.transition(
                session, lead, LeadStatus.OPTED_OUT, reason="the lead asked to stop", actor="system"
            )
        await _cancel_open_outbound(session, lead)
        lead.next_action_at = None
        await session.flush()
        return InboundOutcome(message, opted_out=True, matched_by=how)
    if current != LeadStatus.REPLIED and lead_state.is_allowed(current, LeadStatus.REPLIED):
        await lead_state.transition(
            session, lead, LeadStatus.REPLIED, reason="new inbound message", actor="system"
        )
    return InboundOutcome(message, matched_by=how)


async def _cancel_open_outbound(session: AsyncSession, lead: Lead) -> None:
    await session.execute(
        update(Message)
        .where(
            Message.tenant_id == lead.tenant_id,
            Message.lead_id == lead.id,
            Message.direction == MessageDirection.OUTBOUND.value,
            Message.status.in_(OPEN_OUTBOUND),
        )
        .values(status=MessageStatus.BLOCKED.value, error="opted_out")
        .execution_options(synchronize_session="fetch")
    )


async def apply_status(session: AsyncSession, account_ref: str, update_: StatusUpdate) -> bool:
    """A delivery status webhook → messages.status (never downgrades). Returns True when it changed."""
    connection = await connection_for_account(session, account_ref)
    query = select(Message).where(Message.provider_message_id == update_.provider_message_id)
    if connection is not None:
        query = query.where(Message.tenant_id == connection.tenant_id)
    message = (await session.execute(query)).scalar_one_or_none()
    if message is None or message.direction != MessageDirection.OUTBOUND.value:
        return False
    new = update_.status.value
    current_rank = STATUS_RANK.get(message.status)
    if current_rank is None:
        return False  # failed / blocked / rejected stay as they are
    if new == MessageStatus.FAILED.value:
        if current_rank >= STATUS_RANK[MessageStatus.DELIVERED.value]:
            return False  # a failure report after delivery is noise
        message.status, message.error = new, update_.error or "failed"
    else:
        new_rank = STATUS_RANK.get(new)
        if new_rank is None or new_rank <= current_rank:
            return False  # never downgrade (read → delivered arrives out of order)
        message.status = new
        message.sent_at = message.sent_at or update_.timestamp
    await session.flush()
    return True


# ---------------------------------------------------------------------------------------------- sweeper


async def stuck_queued(session: AsyncSession, now: datetime, older_than: timedelta) -> list[uuid.UUID]:
    """Queued API messages untouched for `older_than` (e.g. the queue was down when they were enqueued).

    Re-enqueueing one that is only waiting for the sending window is harmless: the job checks again.
    """
    rows = await session.execute(
        select(Message.id)
        .where(
            Message.direction == MessageDirection.OUTBOUND.value,
            Message.status.in_(SENDABLE),
            Message.kind != MessageKind.ASSISTED.value,
            Message.updated_at < now - older_than,
        )
        .order_by(Message.updated_at)
        .limit(500)
    )
    return list(rows.scalars())
