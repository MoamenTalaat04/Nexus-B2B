"""Inbound WhatsApp reply worker job (P3-4): classify -> status -> reply agent."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.agents import reply_agent, reply_classifier, reply_tools
from app.core import lead_state
from app.core.tenancy import get_settings_for
from app.core.tracing import agent_run
from app.db import SessionLocal
from app.models.enums import (
    INTENT_TO_STATUS,
    AgentRunKind,
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
from app.models.leads import Lead
from app.models.messaging import Conversation, Message
from app.services import autonomy, knowledge as knowledge_service, messaging
from app.services.notifications import notify_owner

logger = logging.getLogger("app.jobs.inbound")

_STOP_INTENTS = {
    ReplyIntent.OPTED_OUT,
    ReplyIntent.NOT_INTERESTED,
    ReplyIntent.WRONG_CONTACT,
}


async def process_inbound_message(message_id: uuid.UUID) -> dict[str, Any]:
    """Run the full inbound reply pipeline for a stored inbound Message."""
    async with SessionLocal() as session:
        inbound_msg = await session.get(Message, message_id)
        if inbound_msg is None or inbound_msg.direction != MessageDirection.INBOUND.value:
            return {"status": "not_found", "message_id": str(message_id)}

        lead = await session.get(Lead, inbound_msg.lead_id)
        conv = await session.get(Conversation, inbound_msg.conversation_id)
        if lead is None or conv is None:
            return {"status": "missing_lead", "message_id": str(message_id)}

        settings = await get_settings_for(session, inbound_msg.tenant_id)

        if lead.status == LeadStatus.OPTED_OUT.value or lead.agent_paused:
            logger.info("Skipping AI reply for lead %s (status=%s, paused=%s)", lead.id, lead.status, lead.agent_paused)
            return {"status": "skipped", "reason": "paused_or_opted_out"}

        recent_rows = (
            (
                await session.execute(
                    select(Message)
                    .where(Message.conversation_id == conv.id)
                    .order_by(Message.created_at.desc())
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )
        recent_messages = [
            {"direction": m.direction, "body": m.body}
            for m in reversed(recent_rows)
        ]

        outbound_id: uuid.UUID | None = None
        should_enqueue = False

        async with agent_run(
            inbound_msg.tenant_id,
            AgentRunKind.REPLY,
            trigger="webhook",
            input={"message_id": str(inbound_msg.id), "lead_id": str(lead.id)},
        ) as run:
            classification = await reply_classifier.classify_reply(
                run,
                inbound_text=inbound_msg.body,
                recent_messages=recent_messages[:-1],
                language=settings.language,
                lead_id=lead.id,
            )
            inbound_msg.reply_intent = classification.intent.value

            target_status = INTENT_TO_STATUS.get(classification.intent, LeadStatus.REPLIED)
            current_status = LeadStatus(lead.status)
            if target_status != current_status and lead_state.is_allowed(current_status, target_status):
                await lead_state.transition(
                    session,
                    lead,
                    target_status,
                    reason=f"reply_intent:{classification.intent.value}",
                    actor="agent",
                )

            await run.step(
                StepType.DECISION,
                "reply.classified",
                output={
                    "intent": classification.intent.value,
                    "confidence": classification.confidence,
                    "asks_for_human": classification.asks_for_human,
                    "requested_discount": classification.requested_discount_percent,
                },
                lead_id=lead.id,
            )

            if classification.intent in _STOP_INTENTS:
                lead.next_action_at = None
                run.output_summary = {"action": "stopped", "intent": classification.intent.value}
                await session.commit()
                return {"status": "stopped", "intent": classification.intent.value}

            exceeds_discount = (
                classification.requested_discount_percent is not None
                and classification.requested_discount_percent > settings.max_discount_percent
            )
            if classification.asks_for_human or classification.intent == ReplyIntent.WANTS_MANAGEMENT or exceeds_discount:
                lead.agent_paused = True
                reason = (
                    f"Requested {classification.requested_discount_percent}% discount (max {settings.max_discount_percent}%)"
                    if exceeds_discount
                    else "Lead requested human / management follow-up"
                )
                await notify_owner(
                    session,
                    tenant_id=inbound_msg.tenant_id,
                    kind="escalation",
                    title=f"Escalation: {lead.name}",
                    body=f"{reason}. Message: {inbound_msg.body[:200]}",
                )

            hits = await knowledge_service.search(session, inbound_msg.tenant_id, inbound_msg.body, limit=3)
            snippets = "\n".join(f"[{h.filename}]: {h.snippet}" for h in hits)
            tools = reply_tools.build_reply_tools(
                session, tenant_id=inbound_msg.tenant_id, lead=lead, settings=settings
            )

            reply_text = await reply_agent.draft_reply(
                run,
                settings=settings,
                classification=classification,
                recent_messages=recent_messages,
                knowledge_snippets=snippets,
                tools=tools,
                lead_id=lead.id,
            )

            needs_approval = autonomy.needs_approval(settings, OutreachPurpose.REPLY)
            msg_status = (
                MessageStatus.PENDING_APPROVAL.value if needs_approval else MessageStatus.QUEUED.value
            )
            outbound = Message(
                tenant_id=inbound_msg.tenant_id,
                conversation_id=conv.id,
                lead_id=lead.id,
                direction=MessageDirection.OUTBOUND.value,
                channel=ChannelType.WHATSAPP.value,
                author=MessageAuthor.AGENT.value,
                kind=MessageKind.TEXT.value,
                purpose=OutreachPurpose.REPLY.value,
                body=reply_text,
                status=msg_status,
            )
            session.add(outbound)
            await session.flush()
            outbound_id = outbound.id
            should_enqueue = not needs_approval

            run.output_summary = {
                "intent": classification.intent.value,
                "outbound_message_id": str(outbound.id),
                "outbound_status": msg_status,
            }

        await session.commit()

    if should_enqueue and outbound_id is not None:
        await messaging.enqueue_send(outbound_id)

    return {
        "status": "replied",
        "outbound_id": str(outbound_id) if outbound_id else None,
        "queued_for_send": should_enqueue,
    }


async def job_handle_inbound(ctx: dict[str, Any], message_id: str) -> dict[str, Any]:
    """arq entrypoint for inbound WhatsApp reply handling."""
    return await process_inbound_message(uuid.UUID(str(message_id)))
