"""Mock Leads & CRM routes: /leads, /leads/stats, /leads/export.xlsx, /leads/{id} and CRM actions."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from typing import Literal

import openpyxl
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl.styles import Font
from pydantic import BaseModel, Field

from app.core.errors import AppError, NotFoundError
from app.core.security import CurrentUser
from app.mock_api.helpers import (
    get_mock_current_user,
    is_allowed_transition,
    is_eg_mobile,
    normalize_ar,
    normalize_eg_phone,
    paginate,
)
from app.mock_api.state import (
    MockContact,
    MockConversation,
    MockLead,
    MockLeadNote,
    MockLeadOutcome,
    MockLeadStatusHistory,
    MockMessage,
    MockStore,
    get_store,
)
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

router = APIRouter(prefix="/leads", tags=["leads"])


class LeadListItemOut(BaseModel):
    id: uuid.UUID
    name: str
    category: str | None
    governorate: str | None
    city: str | None
    status: str
    score: int | None
    first_score_reason: str | None
    rating: float | None
    reviews_count: int | None
    has_mobile: bool
    agent_paused: bool
    created_at: datetime
    last_inbound_at: datetime | None


class LeadListOut(BaseModel):
    items: list[LeadListItemOut]
    total: int


class LeadsStatsOut(BaseModel):
    total: int
    counts: dict[str, int]


class ContactOut(BaseModel):
    id: uuid.UUID
    type: str
    value: str
    source: str
    is_primary: bool
    confidence: float


class NoteOut(BaseModel):
    id: uuid.UUID
    author_user_id: uuid.UUID
    body: str
    created_at: datetime


class StatusHistoryOut(BaseModel):
    id: uuid.UUID
    from_status: str
    to_status: str
    reason: str
    actor: str
    created_at: datetime


class OutcomeOut(BaseModel):
    id: uuid.UUID
    outcome: str
    value_egp: float | None
    reason: str
    created_at: datetime


class LeadMessageOut(BaseModel):
    id: uuid.UUID
    direction: str
    author: str
    kind: str
    purpose: str | None
    body: str
    status: str
    reply_intent: str | None
    redirected_to: str | None
    sent_at: datetime | None
    created_at: datetime


class LeadDetailOut(BaseModel):
    id: uuid.UUID
    name: str
    source: str
    category: str | None
    address: str | None
    city: str | None
    governorate: str | None
    website: str | None
    google_maps_url: str | None
    rating: float | None
    reviews_count: int | None
    status: str
    score: int | None
    score_reasons: list[str]
    disqualify_reason: str | None
    agent_paused: bool
    ref_code: str
    first_contacted_at: datetime | None
    last_outbound_at: datetime | None
    last_inbound_at: datetime | None
    created_at: datetime
    window_expires_at: datetime | None
    contacts: list[ContactOut]
    messages: list[LeadMessageOut]
    status_history: list[StatusHistoryOut]
    notes: list[NoteOut]
    outcome: OutcomeOut | None


class LeadPatchIn(BaseModel):
    status: LeadStatus | None = None
    agent_paused: bool | None = None
    reason: str | None = None


class NoteCreateIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class OutcomeCreateIn(BaseModel):
    outcome: Literal["won", "lost"]
    value_egp: float | None = Field(default=None, ge=0)
    reason: str = ""


class ContactCreateIn(BaseModel):
    type: ContactType
    value: str = Field(min_length=1, max_length=255)


class ManualMessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


def _lead_has_mobile(store: MockStore, lead_id: uuid.UUID) -> bool:
    return any(
        c.lead_id == lead_id and c.type in {ContactType.MOBILE.value, ContactType.WHATSAPP_LINK.value}
        for c in store.contacts.values()
    )


def _filter_leads(
    store: MockStore,
    tenant_id: uuid.UUID,
    *,
    status: list[str] | None = None,
    min_score: int | None = None,
    q: str | None = None,
    governorate: str | None = None,
    sourcing_run_id: uuid.UUID | None = None,
    sort: str = "score",
) -> list[MockLead]:
    rows = [lead for lead in store.leads.values() if lead.tenant_id == tenant_id]

    if status:
        status_set: set[str] = set()
        for item in status:
            for part in item.split(","):
                p = part.strip()
                if p:
                    status_set.add(p)
        if status_set:
            rows = [r for r in rows if r.status in status_set]

    if min_score is not None:
        rows = [r for r in rows if r.score is not None and r.score >= min_score]

    if governorate:
        gov_lower = governorate.strip().lower()
        rows = [r for r in rows if (r.governorate or "").lower() == gov_lower]

    if sourcing_run_id is not None:
        rows = [r for r in rows if r.sourcing_run_id == sourcing_run_id]

    if q:
        q_norm = normalize_ar(q)
        rows = [
            r
            for r in rows
            if q_norm in normalize_ar(r.name)
            or q_norm in normalize_ar(r.address or "")
            or q_norm in normalize_ar(r.category or "")
            or q_norm in normalize_ar(r.city or "")
        ]

    if sort == "created_at":
        rows.sort(key=lambda r: r.created_at, reverse=True)
    elif sort == "last_inbound_at":
        rows.sort(
            key=lambda r: (r.last_inbound_at is not None, r.last_inbound_at or r.created_at), reverse=True
        )
    else:
        rows.sort(key=lambda r: (r.score is not None, r.score or -1, r.created_at), reverse=True)

    return rows


def _to_list_item(store: MockStore, r: MockLead) -> LeadListItemOut:
    return LeadListItemOut(
        id=r.id,
        name=r.name,
        category=r.category,
        governorate=r.governorate,
        city=r.city,
        status=r.status,
        score=r.score,
        first_score_reason=r.score_reasons[0] if r.score_reasons else None,
        rating=r.rating,
        reviews_count=r.reviews_count,
        has_mobile=_lead_has_mobile(store, r.id),
        agent_paused=r.agent_paused,
        created_at=r.created_at,
        last_inbound_at=r.last_inbound_at,
    )


def _get_tenant_lead(store: MockStore, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> MockLead:
    lead = store.leads.get(lead_id)
    if lead is None or lead.tenant_id != tenant_id:
        raise NotFoundError("lead")
    return lead


@router.get("", response_model=LeadListOut)
async def list_leads(
    status: list[str] | None = Query(default=None),
    min_score: int | None = Query(default=None, ge=0, le=10),
    q: str | None = None,
    governorate: str | None = None,
    sourcing_run_id: uuid.UUID | None = None,
    sort: Literal["score", "created_at", "last_inbound_at"] = "score",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> LeadListOut:
    store = get_store()
    rows = _filter_leads(
        store,
        current_user.tenant_id,
        status=status,
        min_score=min_score,
        q=q,
        governorate=governorate,
        sourcing_run_id=sourcing_run_id,
        sort=sort,
    )
    paged, total = paginate(rows, page, page_size)
    return LeadListOut(items=[_to_list_item(store, r) for r in paged], total=total)


@router.get("/stats", response_model=LeadsStatsOut)
async def leads_stats(current_user: CurrentUser = Depends(get_mock_current_user)) -> LeadsStatsOut:
    store = get_store()
    rows = [lead for lead in store.leads.values() if lead.tenant_id == current_user.tenant_id]
    counts: dict[str, int] = {s.value: 0 for s in LeadStatus}
    for r in rows:
        counts[r.status] = counts.get(r.status, 0) + 1
    return LeadsStatsOut(total=len(rows), counts=counts)


@router.get("/export.xlsx")
async def export_leads_xlsx(
    status: list[str] | None = Query(default=None),
    min_score: int | None = Query(default=None, ge=0, le=10),
    q: str | None = None,
    governorate: str | None = None,
    sourcing_run_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> StreamingResponse:
    store = get_store()
    rows = _filter_leads(
        store,
        current_user.tenant_id,
        status=status,
        min_score=min_score,
        q=q,
        governorate=governorate,
        sourcing_run_id=sourcing_run_id,
    )
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Leads"
    headers = [
        "Name",
        "Status",
        "Score",
        "Governorate",
        "City",
        "Category",
        "Primary Mobile",
        "Website",
        "First Contacted",
        "Last Inbound",
        "Outcome",
        "Value (EGP)",
        "Notes Count",
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"

    for lead in rows:
        primary_mob = next(
            (
                c.value
                for c in store.contacts.values()
                if c.lead_id == lead.id and c.type == ContactType.MOBILE.value and c.is_primary
            ),
            "",
        )
        outcome = next((o for o in store.outcomes.values() if o.lead_id == lead.id), None)
        notes_count = sum(1 for n in store.notes.values() if n.lead_id == lead.id)
        ws.append(
            [
                lead.name,
                lead.status,
                lead.score if lead.score is not None else "",
                lead.governorate or "",
                lead.city or "",
                lead.category or "",
                primary_mob,
                lead.website or "",
                lead.first_contacted_at.isoformat() if lead.first_contacted_at else "",
                lead.last_inbound_at.isoformat() if lead.last_inbound_at else "",
                outcome.outcome if outcome else "",
                outcome.value_egp if outcome and outcome.value_egp is not None else "",
                notes_count,
            ]
        )

    for col in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 42)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="nexus-b2b-leads.xlsx"'},
    )


@router.get("/{lead_id}", response_model=LeadDetailOut)
async def get_lead_detail(
    lead_id: uuid.UUID, current_user: CurrentUser = Depends(get_mock_current_user)
) -> LeadDetailOut:
    store = get_store()
    lead = _get_tenant_lead(store, current_user.tenant_id, lead_id)

    contacts = [c for c in store.contacts.values() if c.lead_id == lead.id]
    messages = sorted(
        (m for m in store.messages.values() if m.lead_id == lead.id),
        key=lambda m: m.created_at,
    )
    history = sorted(
        (h for h in store.status_history.values() if h.lead_id == lead.id),
        key=lambda h: h.created_at,
    )
    notes = sorted(
        (n for n in store.notes.values() if n.lead_id == lead.id),
        key=lambda n: n.created_at,
        reverse=True,
    )
    outcome = next((o for o in store.outcomes.values() if o.lead_id == lead.id), None)
    conv = next((c for c in store.conversations.values() if c.lead_id == lead.id), None)

    return LeadDetailOut(
        id=lead.id,
        name=lead.name,
        source=lead.source,
        category=lead.category,
        address=lead.address,
        city=lead.city,
        governorate=lead.governorate,
        website=lead.website,
        google_maps_url=lead.google_maps_url,
        rating=lead.rating,
        reviews_count=lead.reviews_count,
        status=lead.status,
        score=lead.score,
        score_reasons=list(lead.score_reasons),
        disqualify_reason=lead.disqualify_reason,
        agent_paused=lead.agent_paused,
        ref_code=lead.ref_code,
        first_contacted_at=lead.first_contacted_at,
        last_outbound_at=lead.last_outbound_at,
        last_inbound_at=lead.last_inbound_at,
        created_at=lead.created_at,
        window_expires_at=conv.window_expires_at if conv else None,
        contacts=[
            ContactOut(
                id=c.id,
                type=c.type,
                value=c.value,
                source=c.source,
                is_primary=c.is_primary,
                confidence=c.confidence,
            )
            for c in contacts
        ],
        messages=[
            LeadMessageOut(
                id=m.id,
                direction=m.direction,
                author=m.author,
                kind=m.kind,
                purpose=m.purpose,
                body=m.body,
                status=m.status,
                reply_intent=m.reply_intent,
                redirected_to=m.redirected_to,
                sent_at=m.sent_at,
                created_at=m.created_at,
            )
            for m in messages
        ],
        status_history=[
            StatusHistoryOut(
                id=h.id,
                from_status=h.from_status,
                to_status=h.to_status,
                reason=h.reason,
                actor=h.actor,
                created_at=h.created_at,
            )
            for h in history
        ],
        notes=[
            NoteOut(id=n.id, author_user_id=n.author_user_id, body=n.body, created_at=n.created_at)
            for n in notes
        ],
        outcome=(
            OutcomeOut(
                id=outcome.id,
                outcome=outcome.outcome,
                value_egp=outcome.value_egp,
                reason=outcome.reason,
                created_at=outcome.created_at,
            )
            if outcome
            else None
        ),
    )


@router.patch("/{lead_id}", response_model=LeadDetailOut)
async def patch_lead(
    lead_id: uuid.UUID,
    body: LeadPatchIn,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> LeadDetailOut:
    store = get_store()
    lead = _get_tenant_lead(store, current_user.tenant_id, lead_id)
    now = datetime.now(UTC)

    if body.status is not None and body.status.value != lead.status:
        current = LeadStatus(lead.status)
        if not is_allowed_transition(current, body.status, force=True):
            raise AppError(
                "invalid_transition", f"Cannot transition from {current.value} to {body.status.value}", 409
            )
        h_id = uuid.uuid4()
        store.status_history[h_id] = MockLeadStatusHistory(
            id=h_id,
            tenant_id=current_user.tenant_id,
            lead_id=lead.id,
            from_status=lead.status,
            to_status=body.status.value,
            reason=body.reason or "manual",
            actor="user",
            actor_user_id=current_user.user_id,
            created_at=now,
        )
        lead.status = body.status.value

    if body.agent_paused is not None and body.agent_paused != lead.agent_paused:
        lead.agent_paused = body.agent_paused
        h_id = uuid.uuid4()
        store.status_history[h_id] = MockLeadStatusHistory(
            id=h_id,
            tenant_id=current_user.tenant_id,
            lead_id=lead.id,
            from_status=lead.status,
            to_status=lead.status,
            reason="agent_paused" if body.agent_paused else "agent_resumed",
            actor="user",
            actor_user_id=current_user.user_id,
            created_at=now,
        )

    return await get_lead_detail(lead_id, current_user)


@router.post("/{lead_id}/notes", response_model=NoteOut, status_code=201)
async def add_note(
    lead_id: uuid.UUID,
    body: NoteCreateIn,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> NoteOut:
    store = get_store()
    lead = _get_tenant_lead(store, current_user.tenant_id, lead_id)
    note = MockLeadNote(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        lead_id=lead.id,
        author_user_id=current_user.user_id,
        body=body.body.strip(),
        created_at=datetime.now(UTC),
    )
    store.notes[note.id] = note
    return NoteOut(id=note.id, author_user_id=note.author_user_id, body=note.body, created_at=note.created_at)


@router.post("/{lead_id}/outcome", response_model=OutcomeOut, status_code=201)
async def record_outcome(
    lead_id: uuid.UUID,
    body: OutcomeCreateIn,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> OutcomeOut:
    store = get_store()
    lead = _get_tenant_lead(store, current_user.tenant_id, lead_id)
    now = datetime.now(UTC)

    # Remove previous outcome if re-recorded
    for oid in [k for k, v in store.outcomes.items() if v.lead_id == lead.id]:
        del store.outcomes[oid]

    outcome = MockLeadOutcome(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        lead_id=lead.id,
        outcome=body.outcome,
        value_egp=body.value_egp,
        reason=body.reason,
        created_at=now,
    )
    store.outcomes[outcome.id] = outcome

    target_status = LeadStatus.WON.value if body.outcome == "won" else LeadStatus.LOST.value
    if lead.status != target_status:
        h_id = uuid.uuid4()
        store.status_history[h_id] = MockLeadStatusHistory(
            id=h_id,
            tenant_id=current_user.tenant_id,
            lead_id=lead.id,
            from_status=lead.status,
            to_status=target_status,
            reason=body.reason or f"Marked {body.outcome}",
            actor="user",
            actor_user_id=current_user.user_id,
            created_at=now,
        )
        lead.status = target_status
    lead.agent_paused = True

    return OutcomeOut(
        id=outcome.id,
        outcome=outcome.outcome,
        value_egp=outcome.value_egp,
        reason=outcome.reason,
        created_at=outcome.created_at,
    )


@router.post("/{lead_id}/contacts", response_model=ContactOut, status_code=201)
async def add_contact(
    lead_id: uuid.UUID,
    body: ContactCreateIn,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> ContactOut:
    store = get_store()
    lead = _get_tenant_lead(store, current_user.tenant_id, lead_id)
    now = datetime.now(UTC)

    val = body.value.strip()
    if body.type == ContactType.MOBILE:
        e164 = normalize_eg_phone(val)
        if not e164 or not is_eg_mobile(e164):
            raise AppError(
                "invalid_phone", "Provide a valid Egyptian mobile number (+20 10/11/12/15...).", 422
            )
        val = e164

    is_first_of_type = not any(
        c.lead_id == lead.id and c.type == body.type.value for c in store.contacts.values()
    )
    contact = MockContact(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        lead_id=lead.id,
        type=body.type.value,
        value=val,
        source="manual",
        is_primary=is_first_of_type,
        confidence=1.0,
        created_at=now,
    )
    store.contacts[contact.id] = contact

    if body.type == ContactType.MOBILE and lead.status == LeadStatus.NO_CONTACT.value:
        h_id = uuid.uuid4()
        store.status_history[h_id] = MockLeadStatusHistory(
            id=h_id,
            tenant_id=current_user.tenant_id,
            lead_id=lead.id,
            from_status=lead.status,
            to_status=LeadStatus.ENRICHED.value,
            reason="Manual mobile contact added",
            actor="user",
            actor_user_id=current_user.user_id,
            created_at=now,
        )
        lead.status = LeadStatus.ENRICHED.value

    return ContactOut(
        id=contact.id,
        type=contact.type,
        value=contact.value,
        source=contact.source,
        is_primary=contact.is_primary,
        confidence=contact.confidence,
    )


@router.post("/{lead_id}/messages", response_model=LeadMessageOut, status_code=201)
async def send_manual_message(
    lead_id: uuid.UUID,
    body: ManualMessageIn,
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> LeadMessageOut:
    store = get_store()
    lead = _get_tenant_lead(store, current_user.tenant_id, lead_id)
    now = datetime.now(UTC)

    if lead.status == LeadStatus.OPTED_OUT.value:
        raise AppError("lead_opted_out", "This lead opted out and cannot receive messages.", status_code=409)

    conv = next((c for c in store.conversations.values() if c.lead_id == lead.id), None)
    if conv is None or conv.window_expires_at is None or conv.window_expires_at <= now:
        raise AppError(
            "window_closed",
            "The 24h WhatsApp customer-service window is closed. Send an approved template instead.",
            status_code=409,
        )

    msg = MockMessage(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        conversation_id=conv.id,
        lead_id=lead.id,
        direction=MessageDirection.OUTBOUND.value,
        channel=ChannelType.WHATSAPP.value,
        author=MessageAuthor.HUMAN.value,
        kind=MessageKind.TEXT.value,
        purpose=OutreachPurpose.REPLY.value,
        body=body.body.strip(),
        status=MessageStatus.SENT.value,
        provider_message_id=f"wamid.mock.manual.{uuid.uuid4().hex[:10]}",
        sent_at=now,
        created_at=now,
    )
    store.messages[msg.id] = msg
    lead.last_outbound_at = now
    if lead.first_contacted_at is None:
        lead.first_contacted_at = now

    return LeadMessageOut(
        id=msg.id,
        direction=msg.direction,
        author=msg.author,
        kind=msg.kind,
        purpose=msg.purpose,
        body=msg.body,
        status=msg.status,
        reply_intent=msg.reply_intent,
        redirected_to=msg.redirected_to,
        sent_at=msg.sent_at,
        created_at=msg.created_at,
    )


def ensure_conversation(
    store: MockStore, tenant_id: uuid.UUID, lead: MockLead, contact_value: str
) -> MockConversation:
    conv = next((c for c in store.conversations.values() if c.lead_id == lead.id), None)
    if conv is None:
        conv = MockConversation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            lead_id=lead.id,
            channel=ChannelType.WHATSAPP.value,
            contact_value=contact_value,
            created_at=datetime.now(UTC),
        )
        store.conversations[conv.id] = conv
    return conv
