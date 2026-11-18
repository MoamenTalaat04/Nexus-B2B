"""Messaging service (CONTRACTS section 9) — STAND-IN, NEVER SENDS ANYTHING.

Written in P3-3 so the outreach engine can be built and tested before B's P3-2 lands. It follows the
contract's signatures and status rules, but:
- create_outbound / approve_message leave messages `queued` and do NOT enqueue job_send_message
  (that job does not exist yet), so nothing is ever sent;
- send_message is a no-op that logs;
- resolve_demo_target picks a whitelisted phone deterministically and does not write demo_routes.
B (P3-2) owns this file and replaces it with the real implementation (mock/real channel, demo routing, caps).
"""

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.models.enums import (
    ChannelType,
    ContactType,
    LeadStatus,
    MessageAuthor,
    MessageDirection,
    MessageKind,
    MessageStatus,
    OutreachPurpose,
)
from app.models.leads import Contact, Lead
from app.models.messaging import ChannelConnection, Conversation, Message, MessageTemplate
from app.models.tenants import BusinessSettings

logger = logging.getLogger("app.services.messaging")

ASSISTANT_PREFILL_AR = "أهلاً، حابب أعرف أكتر عن منتجاتكم"


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


async def _conversation(session: AsyncSession, lead: Lead) -> Conversation:
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
            contact_value=await primary_mobile(session, lead.tenant_id, lead.id) or "",
        )
        session.add(conv)
        await session.flush()
    return conv


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
        status = MessageStatus.QUEUED  # TODO(P3-2): enqueue job_send_message(message_id)
    message = Message(
        tenant_id=tenant_id,
        conversation_id=conv.id,
        lead_id=lead_id,
        direction=MessageDirection.OUTBOUND.value,
        channel=ChannelType.WHATSAPP.value,
        author=author.value,
        kind=kind.value,
        purpose=purpose.value,
        template_name=template_name,
        template_params=template_params,
        body=body,
        status=status.value,
        error=error,
        agent_run_id=agent_run_id,
    )
    session.add(message)
    await session.flush()
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
    message.status = MessageStatus.QUEUED.value  # TODO(P3-2): enqueue job_send_message(message_id)
    await session.flush()
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
    await session.flush()
    from app.services import outreach  # local import: outreach imports this module

    await outreach.on_message_sent(session, message)
    return message


async def send_message(message_id: uuid.UUID) -> None:
    """Job body (P3-2). Stand-in: does nothing, so no message is ever sent before B's real version lands."""
    logger.warning(
        "messaging.send_message is a stand-in (P3-2 not merged); message %s was not sent", message_id
    )


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


def resolve_demo_target(settings: BusinessSettings, lead_id: uuid.UUID) -> str | None:
    """A whitelisted test phone for this lead (stable per lead). Stand-in: does not write demo_routes."""
    whitelist = [str(p) for p in (settings.demo_whitelist or [])]
    if not whitelist:
        return None
    index = int(hashlib.sha256(str(lead_id).encode()).hexdigest(), 16) % len(whitelist)
    return whitelist[index]


async def get_whatsapp_connection(session: AsyncSession, tenant_id: uuid.UUID) -> ChannelConnection | None:
    return (
        await session.execute(
            select(ChannelConnection).where(
                ChannelConnection.tenant_id == tenant_id,
                ChannelConnection.channel == ChannelType.WHATSAPP.value,
            )
        )
    ).scalar_one_or_none()
