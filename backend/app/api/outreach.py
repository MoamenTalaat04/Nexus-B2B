"""Outreach API (CONTRACTS section 11, P3-3): the approval queue and assisted sending.

GET  /api/v1/outreach/queue                      pending_approval messages + lead info + rationale + preview
POST /api/v1/outreach/messages/{id}/approve      {params?, body?} → validated, then queued for sending
POST /api/v1/outreach/messages/{id}/reject       reject + pause the agent for that lead (QUEUED → ENRICHED)
POST /api/v1/outreach/approve-bulk               {ids} → {"approved": [...], "failed": [{id, error}]}
GET  /api/v1/outreach/assisted                   awaiting_manual_send messages + wa_link + "x of y sent today"
POST /api/v1/outreach/messages/{id}/mark-sent    {body?} the owner sent it from their phone → lead CONTACTED
Skip in assisted mode = the reject endpoint.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.message_personalizer import param_problems
from app.core.errors import AppError
from app.core.security import CurrentUser, get_current_user
from app.core.tenancy import get_settings_for
from app.db import get_session
from app.models.enums import MessageStatus, StepType
from app.models.leads import Lead
from app.models.messaging import Message, MessageTemplate
from app.models.runs import AgentStep
from app.models.tenants import BusinessSettings
from app.services import messaging, outreach

router = APIRouter(prefix="/outreach", tags=["outreach"])


class LeadInfo(BaseModel):
    id: uuid.UUID
    name: str
    category: str | None
    city: str | None
    governorate: str | None
    rating: float | None
    score: int | None
    score_reasons: list[str]
    status: str


class OutreachItem(BaseModel):
    id: uuid.UUID
    status: str
    kind: str
    purpose: str | None
    body: str
    template_name: str | None
    template_params: list[str] | None
    template_body: str | None = None
    param_count: int | None = None
    rationale: str | None
    created_at: datetime
    lead: LeadInfo


class AssistedItem(OutreachItem):
    wa_link: str | None
    wa_link_error: str | None = None  # demo_whitelist_empty | no_mobile


class QueueOut(BaseModel):
    items: list[OutreachItem]
    total: int


class AssistedOut(BaseModel):
    items: list[AssistedItem]
    total: int
    sent_today: int
    daily_cap: int


class ApproveIn(BaseModel):
    params: list[str] | None = None
    body: str | None = None


class BulkIn(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class BulkOut(BaseModel):
    approved: list[uuid.UUID]
    failed: list[dict[str, str]]


class MarkSentIn(BaseModel):
    body: str | None = None  # the final text, if the owner edited it before sending


class SimulateInboundIn(BaseModel):
    lead_id: uuid.UUID
    text: str = Field(min_length=1, max_length=2000)


class SimulateInboundOut(BaseModel):
    inbound_message_id: uuid.UUID
    pipeline: dict[str, Any]


# ---------------------------------------------------------------------------------------------- helpers


async def _messages(
    session: AsyncSession, tenant_id: uuid.UUID, status: MessageStatus
) -> list[tuple[Message, Lead]]:
    rows = await session.execute(
        select(Message, Lead)
        .join(Lead, Lead.id == Message.lead_id)
        .where(Message.tenant_id == tenant_id, Lead.tenant_id == tenant_id, Message.status == status.value)
        .order_by(Message.created_at)
    )
    return [(m, lead) for m, lead in rows.all()]


async def _rationales(session: AsyncSession, tenant_id: uuid.UUID, ids: list[uuid.UUID]) -> dict[str, str]:
    """The personalizer's rationale, recorded on the outreach run's "outreach.message" step."""
    if not ids:
        return {}
    rows = await session.execute(
        select(AgentStep.output).where(
            AgentStep.tenant_id == tenant_id,
            AgentStep.step_type == StepType.DECISION.value,
            AgentStep.name == "outreach.message",
            AgentStep.output["message_id"].astext.in_([str(i) for i in ids]),
        )
    )
    return {str(o["message_id"]): str(o.get("rationale") or "") for o in rows.scalars() if o}


async def _templates(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, MessageTemplate]:
    rows = await session.execute(select(MessageTemplate).where(MessageTemplate.tenant_id == tenant_id))
    return {t.name: t for t in rows.scalars()}


def _lead(lead: Lead) -> LeadInfo:
    return LeadInfo(
        id=lead.id,
        name=lead.name,
        category=lead.category,
        city=lead.city,
        governorate=lead.governorate,
        rating=lead.rating,
        score=lead.score,
        score_reasons=list(lead.score_reasons or []),
        status=lead.status,
    )


def _item(
    message: Message, lead: Lead, rationale: str | None, template: MessageTemplate | None
) -> dict[str, Any]:
    return {
        "id": message.id,
        "status": message.status,
        "kind": message.kind,
        "purpose": message.purpose,
        "body": message.body,
        "template_name": message.template_name,
        "template_params": message.template_params,
        "template_body": template.body_text if template else None,
        "param_count": template.param_count if template else None,
        "rationale": rationale,
        "created_at": message.created_at,
        "lead": _lead(lead),
    }


async def _wa_link(
    session: AsyncSession, settings: BusinessSettings, lead: Lead, text: str
) -> tuple[str | None, str | None]:
    if settings.demo_mode:
        target = messaging.resolve_demo_target(settings, lead.id)
        if target is None:
            return None, "demo_whitelist_empty"
    else:
        target = await messaging.primary_mobile(session, lead.tenant_id, lead.id)
        if target is None:
            return None, "no_mobile"
    return messaging.build_wa_link(target, text), None


async def _validate_params(
    session: AsyncSession, tenant_id: uuid.UUID, message_id: uuid.UUID, params: list[str]
) -> None:
    message = (
        await session.execute(select(Message).where(Message.id == message_id, Message.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if message is None or message.template_name is None:
        return  # messaging reports not-found; non-template messages have no params to check
    template = (await _templates(session, tenant_id)).get(message.template_name)
    count = template.param_count if template else len(message.template_params or [])
    problems = param_problems(params, count)
    if problems:
        raise AppError(
            "invalid_params", "The edited message cannot be sent: " + "; ".join(problems) + ".", 400
        )


# ---------------------------------------------------------------------------------------------- routes


@router.get("/queue", response_model=QueueOut)
async def get_queue(
    user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> QueueOut:
    rows = await _messages(session, user.tenant_id, MessageStatus.PENDING_APPROVAL)
    rationales = await _rationales(session, user.tenant_id, [m.id for m, _ in rows])
    templates = await _templates(session, user.tenant_id)
    items = [
        OutreachItem(**_item(m, lead, rationales.get(str(m.id)), templates.get(m.template_name or "")))
        for m, lead in rows
    ]
    return QueueOut(items=items, total=len(items))


@router.post("/messages/{message_id}/approve", response_model=OutreachItem)
async def approve(
    message_id: uuid.UUID,
    body: ApproveIn | None = None,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OutreachItem:
    edits = body or ApproveIn()
    if edits.params is not None:
        await _validate_params(session, user.tenant_id, message_id, edits.params)
    message = await messaging.approve_message(
        session,
        tenant_id=user.tenant_id,
        message_id=message_id,
        user_id=user.user_id,
        edited_params=edits.params,
        edited_body=edits.body,
    )
    await session.commit()
    lead = await session.get(Lead, message.lead_id)
    assert lead is not None
    template = (await _templates(session, user.tenant_id)).get(message.template_name or "")
    rationale = (await _rationales(session, user.tenant_id, [message.id])).get(str(message.id))
    return OutreachItem(**_item(message, lead, rationale, template))


@router.post("/messages/{message_id}/reject", response_model=OutreachItem)
async def reject(
    message_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OutreachItem:
    message = await outreach.reject(
        session, tenant_id=user.tenant_id, message_id=message_id, user_id=user.user_id
    )
    await session.commit()
    lead = await session.get(Lead, message.lead_id)
    assert lead is not None
    return OutreachItem(**_item(message, lead, None, None))


@router.post("/approve-bulk", response_model=BulkOut)
async def approve_bulk(
    body: BulkIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BulkOut:
    approved: list[uuid.UUID] = []
    failed: list[dict[str, str]] = []
    for message_id in dict.fromkeys(body.ids):  # unique, order kept
        try:
            await messaging.approve_message(
                session, tenant_id=user.tenant_id, message_id=message_id, user_id=user.user_id
            )
            approved.append(message_id)
        except AppError as exc:
            failed.append({"id": str(message_id), "error": exc.code})
    await session.commit()
    return BulkOut(approved=approved, failed=failed)


@router.get("/assisted", response_model=AssistedOut)
async def get_assisted(
    user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> AssistedOut:
    settings = await get_settings_for(session, user.tenant_id)
    rows = await _messages(session, user.tenant_id, MessageStatus.AWAITING_MANUAL_SEND)
    rationales = await _rationales(session, user.tenant_id, [m.id for m, _ in rows])
    items: list[AssistedItem] = []
    for message, lead in rows:
        link, link_error = await _wa_link(session, settings, lead, message.body)
        items.append(
            AssistedItem(
                **_item(message, lead, rationales.get(str(message.id)), None),
                wa_link=link,
                wa_link_error=link_error,
            )
        )
    return AssistedOut(
        items=items,
        total=len(items),
        sent_today=await outreach.sent_today(session, user.tenant_id, datetime.now(UTC)),
        daily_cap=settings.daily_send_cap,
    )


@router.post("/messages/{message_id}/mark-sent", response_model=OutreachItem)
async def mark_sent(
    message_id: uuid.UUID,
    body: MarkSentIn | None = None,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OutreachItem:
    if body is not None and body.body is not None:
        if not body.body.strip():
            raise AppError("invalid_body", "The message text cannot be empty.", 400)
        found = (
            await session.execute(
                select(Message).where(Message.id == message_id, Message.tenant_id == user.tenant_id)
            )
        ).scalar_one_or_none()
        if found is not None and found.status == MessageStatus.AWAITING_MANUAL_SEND.value:
            found.body = body.body
    message = await messaging.mark_sent_manually(
        session, tenant_id=user.tenant_id, message_id=message_id, user_id=user.user_id
    )
    await session.commit()
    lead = await session.get(Lead, message.lead_id)
    assert lead is not None
    return OutreachItem(**_item(message, lead, None, None))


@router.post("/simulate-inbound", response_model=SimulateInboundOut, status_code=201)
async def simulate_inbound_reply(
    body: SimulateInboundIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SimulateInboundOut:
    """Demo/testing helper: simulate an inbound lead reply and run the Reply Agent pipeline."""
    from datetime import timedelta

    from app.core import lead_state
    from app.models.enums import ChannelType, LeadStatus, MessageAuthor, MessageDirection, MessageKind
    from app.models.messaging import Conversation
    from app.workers.jobs.inbound import process_inbound_message

    lead = (
        await session.execute(select(Lead).where(Lead.id == body.lead_id, Lead.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if lead is None:
        raise AppError("not_found", "Lead not found.", status_code=404)

    conv = (
        await session.execute(
            select(Conversation).where(Conversation.lead_id == lead.id, Conversation.tenant_id == user.tenant_id)
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if conv is None:
        conv = Conversation(
            tenant_id=user.tenant_id,
            lead_id=lead.id,
            channel=ChannelType.WHATSAPP.value,
            contact_value="simulated",
            window_expires_at=now + timedelta(hours=24),
        )
        session.add(conv)
        await session.flush()
    else:
        conv.window_expires_at = now + timedelta(hours=24)

    inbound_msg = Message(
        tenant_id=user.tenant_id,
        conversation_id=conv.id,
        lead_id=lead.id,
        direction=MessageDirection.INBOUND.value,
        channel=ChannelType.WHATSAPP.value,
        author=MessageAuthor.LEAD.value,
        kind=MessageKind.TEXT.value,
        body=body.text.strip(),
        status=MessageStatus.RECEIVED.value,
        provider_message_id=f"sim:{uuid.uuid4()}",
        sent_at=now,
    )
    session.add(inbound_msg)
    lead.last_inbound_at = now
    current = LeadStatus(lead.status)
    if current != LeadStatus.REPLIED and lead_state.is_allowed(current, LeadStatus.REPLIED):
        await lead_state.transition(session, lead, LeadStatus.REPLIED, reason="simulated inbound", actor="user")
    await session.commit()
    await session.refresh(inbound_msg)

    pipeline_result = await process_inbound_message(inbound_msg.id)
    return SimulateInboundOut(inbound_message_id=inbound_msg.id, pipeline=pipeline_result)
