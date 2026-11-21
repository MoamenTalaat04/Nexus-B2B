"""Mock Outreach & Approval Queue routes: /outreach/*."""

from __future__ import annotations

import urllib.parse
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.api.outreach import (
    ApproveIn,
    AssistedItem,
    AssistedOut,
    BulkIn,
    BulkOut,
    LeadInfo,
    MarkSentIn,
    OutreachItem,
    QueueOut,
)
from app.core.errors import AppError, NotFoundError
from app.core.security import CurrentUser
from app.mock_api.helpers import get_mock_current_user, get_tenant_settings
from app.mock_api.state import (
    MockLead,
    MockLeadStatusHistory,
    MockMessage,
    MockMessageTemplate,
    MockStore,
    get_store,
)
from app.models.enums import ContactType, LeadStatus, MessageStatus, OutreachPurpose

router = APIRouter(prefix="/outreach", tags=["outreach"])


def _lead_info(lead: MockLead) -> LeadInfo:
    return LeadInfo(
        id=lead.id,
        name=lead.name,
        category=lead.category,
        city=lead.city,
        governorate=lead.governorate,
        rating=lead.rating,
        score=lead.score,
        score_reasons=list(lead.score_reasons),
        status=lead.status,
    )


def _find_template(store: MockStore, tenant_id: uuid.UUID, name: str | None) -> MockMessageTemplate | None:
    if not name:
        return None
    return next((t for t in store.templates.values() if t.tenant_id == tenant_id and t.name == name), None)


def _to_outreach_item(store: MockStore, msg: MockMessage, lead: MockLead) -> OutreachItem:
    tpl = _find_template(store, msg.tenant_id, msg.template_name)
    return OutreachItem(
        id=msg.id,
        status=msg.status,
        kind=msg.kind,
        purpose=msg.purpose,
        body=msg.body,
        template_name=msg.template_name,
        template_params=msg.template_params,
        template_body=tpl.body_text if tpl else None,
        param_count=tpl.param_count if tpl else None,
        rationale=msg.rationale,
        created_at=msg.created_at,
        lead=_lead_info(lead),
    )


def _render_template(body_text: str, params: list[str]) -> str:
    rendered = body_text
    for idx, val in enumerate(params, start=1):
        rendered = rendered.replace(f"{{{{{idx}}}}}", val)
    return rendered


@router.get("/queue", response_model=QueueOut)
async def get_queue(current_user: CurrentUser = Depends(get_mock_current_user)) -> QueueOut:
    store = get_store()
    msgs = [
        m
        for m in store.messages.values()
        if m.tenant_id == current_user.tenant_id and m.status == MessageStatus.PENDING_APPROVAL.value
    ]
    msgs.sort(key=lambda m: m.created_at)
    items = [_to_outreach_item(store, m, store.leads[m.lead_id]) for m in msgs if m.lead_id in store.leads]
    return QueueOut(items=items, total=len(items))


@router.post("/messages/{message_id}/approve", response_model=OutreachItem)
async def approve_message(
    message_id: uuid.UUID,
    body: ApproveIn | None = None,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> OutreachItem:
    store = get_store()
    msg = store.messages.get(message_id)
    if msg is None or msg.tenant_id != current_user.tenant_id:
        raise NotFoundError("message")
    if msg.status != MessageStatus.PENDING_APPROVAL.value:
        raise AppError("invalid_message_status", f"Message is {msg.status}, not pending_approval.", 409)

    lead = store.leads[msg.lead_id]
    if lead.status == LeadStatus.OPTED_OUT.value:
        msg.status = MessageStatus.BLOCKED.value
        raise AppError("lead_opted_out", "Lead opted out.", 409)

    if body and body.params is not None:
        tpl = _find_template(store, current_user.tenant_id, msg.template_name)
        if tpl and len(body.params) != tpl.param_count:
            raise AppError("invalid_params", f"Expected {tpl.param_count} template parameters.", 422)
        msg.template_params = body.params
        if tpl:
            msg.body = _render_template(tpl.body_text, body.params)
    elif body and body.body is not None:
        msg.body = body.body.strip()

    now = datetime.now(UTC)
    s = get_tenant_settings(store, current_user.tenant_id)
    msg.approved_by_user_id = current_user.user_id
    msg.status = MessageStatus.SENT.value
    msg.sent_at = now
    msg.provider_message_id = f"wamid.mock.{uuid.uuid4().hex[:10]}"
    if s.demo_mode and s.demo_whitelist:
        msg.redirected_to = s.demo_whitelist[0]

    lead.last_outbound_at = now
    if lead.first_contacted_at is None:
        lead.first_contacted_at = now
    if lead.status in {LeadStatus.QUEUED.value, LeadStatus.LATER.value, LeadStatus.ENRICHED.value}:
        h_id = uuid.uuid4()
        store.status_history[h_id] = MockLeadStatusHistory(
            id=h_id,
            tenant_id=current_user.tenant_id,
            lead_id=lead.id,
            from_status=lead.status,
            to_status=LeadStatus.CONTACTED.value,
            reason="Outreach message approved and sent",
            actor="agent",
            created_at=now,
        )
        lead.status = LeadStatus.CONTACTED.value

    return _to_outreach_item(store, msg, lead)


@router.post("/messages/{message_id}/reject", response_model=OutreachItem)
async def reject_message(
    message_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> OutreachItem:
    store = get_store()
    msg = store.messages.get(message_id)
    if msg is None or msg.tenant_id != current_user.tenant_id:
        raise NotFoundError("message")
    if msg.status not in {MessageStatus.PENDING_APPROVAL.value, MessageStatus.AWAITING_MANUAL_SEND.value}:
        raise AppError("invalid_message_status", f"Cannot reject message in status {msg.status}.", 409)

    now = datetime.now(UTC)
    msg.status = MessageStatus.REJECTED.value
    lead = store.leads[msg.lead_id]
    if lead.status == LeadStatus.QUEUED.value:
        h_id = uuid.uuid4()
        store.status_history[h_id] = MockLeadStatusHistory(
            id=h_id,
            tenant_id=current_user.tenant_id,
            lead_id=lead.id,
            from_status=lead.status,
            to_status=LeadStatus.ENRICHED.value,
            reason="Outreach message rejected by user",
            actor="user",
            actor_user_id=current_user.user_id,
            created_at=now,
        )
        lead.status = LeadStatus.ENRICHED.value
    lead.agent_paused = True
    return _to_outreach_item(store, msg, lead)


@router.post("/approve-bulk", response_model=BulkOut)
async def approve_bulk(
    body: BulkIn,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> BulkOut:
    approved: list[uuid.UUID] = []
    failed: list[dict[str, str]] = []
    for mid in body.ids:
        try:
            await approve_message(mid, None, current_user)
            approved.append(mid)
        except AppError as exc:
            failed.append({"id": str(mid), "error": exc.message})
    return BulkOut(approved=approved, failed=failed)


@router.get("/assisted", response_model=AssistedOut)
async def get_assisted(current_user: CurrentUser = Depends(get_mock_current_user)) -> AssistedOut:
    store = get_store()
    s = get_tenant_settings(store, current_user.tenant_id)
    msgs = [
        m
        for m in store.messages.values()
        if m.tenant_id == current_user.tenant_id and m.status == MessageStatus.AWAITING_MANUAL_SEND.value
    ]
    msgs.sort(key=lambda m: m.created_at)

    today = datetime.now(UTC).date()
    sent_today = sum(
        1
        for m in store.messages.values()
        if m.tenant_id == current_user.tenant_id
        and m.purpose in {OutreachPurpose.FIRST_TOUCH.value, OutreachPurpose.FOLLOWUP.value}
        and m.sent_at is not None
        and m.sent_at.date() == today
    )

    items: list[AssistedItem] = []
    for m in msgs:
        lead = store.leads.get(m.lead_id)
        if not lead:
            continue
        base = _to_outreach_item(store, m, lead)
        if s.demo_mode:
            target = s.demo_whitelist[0] if s.demo_whitelist else None
            err = "demo_whitelist_empty" if not target else None
        else:
            target = next(
                (
                    c.value
                    for c in store.contacts.values()
                    if c.lead_id == lead.id and c.type == ContactType.MOBILE.value and c.is_primary
                ),
                None,
            )
            err = "no_mobile" if not target else None

        wa_link = None
        if target:
            digits = target.lstrip("+")
            wa_link = f"https://wa.me/{digits}?text={urllib.parse.quote(m.body)}"

        items.append(AssistedItem(**base.model_dump(), wa_link=wa_link, wa_link_error=err))

    return AssistedOut(items=items, total=len(items), sent_today=sent_today, daily_cap=s.daily_send_cap)


@router.post("/messages/{message_id}/mark-sent", response_model=OutreachItem)
async def mark_sent_manually(
    message_id: uuid.UUID,
    body: MarkSentIn | None = None,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> OutreachItem:
    store = get_store()
    msg = store.messages.get(message_id)
    if msg is None or msg.tenant_id != current_user.tenant_id:
        raise NotFoundError("message")
    if msg.status != MessageStatus.AWAITING_MANUAL_SEND.value:
        raise AppError("invalid_message_status", f"Message is {msg.status}, not awaiting_manual_send.", 409)

    if body and body.body:
        msg.body = body.body.strip()

    now = datetime.now(UTC)
    msg.status = MessageStatus.SENT.value
    msg.sent_at = now
    msg.approved_by_user_id = current_user.user_id

    lead = store.leads[msg.lead_id]
    lead.last_outbound_at = now
    if lead.first_contacted_at is None:
        lead.first_contacted_at = now
    if lead.status in {LeadStatus.QUEUED.value, LeadStatus.LATER.value, LeadStatus.ENRICHED.value}:
        h_id = uuid.uuid4()
        store.status_history[h_id] = MockLeadStatusHistory(
            id=h_id,
            tenant_id=current_user.tenant_id,
            lead_id=lead.id,
            from_status=lead.status,
            to_status=LeadStatus.CONTACTED.value,
            reason="Assisted message sent manually by user",
            actor="user",
            actor_user_id=current_user.user_id,
            created_at=now,
        )
        lead.status = LeadStatus.CONTACTED.value

    return _to_outreach_item(store, msg, lead)
