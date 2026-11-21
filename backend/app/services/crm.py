"""Built-in CRM (P4-1, CONTRACTS section 11 CRM routes): lead detail, status/pause, notes, outcomes, manual
contacts, manual WhatsApp messages and the Excel export. Every query is tenant-scoped.

Rules:
- Status changes go through lead_state.transition(actor="user", force=True, reason="manual").
- Opt-out is final: a lead that opted out cannot be moved to another status or messaged from here.
- An outcome (won/lost) moves the lead to WON/LOST, pauses the agent, and after the commit tells the feedback
  loop (insights.on_outcome_recorded). Recording an outcome again replaces the earlier one (one per lead).
- A manual message is free text, so it is allowed only inside the 24h customer-service window.
"""

import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.core import lead_state
from app.core.errors import AppError, NotFoundError
from app.core.phones import is_eg_mobile, normalize_eg_phone
from app.models.enums import (
    ContactType,
    LeadStatus,
    MessageAuthor,
    MessageDirection,
    MessageKind,
    OutreachPurpose,
)
from app.models.leads import Contact, Lead, LeadNote, LeadOutcome, LeadStatusHistory
from app.models.messaging import Conversation, Message
from app.services import insights, messaging

# ------------------------------------------------------------------------------------------------ schemas


class ContactOut(BaseModel):
    id: uuid.UUID
    type: str
    value: str
    source: str
    is_primary: bool
    confidence: float


class MessageOut(BaseModel):
    id: uuid.UUID
    direction: str
    author: str
    kind: str
    purpose: str | None
    status: str
    body: str
    template_name: str | None
    reply_intent: str | None
    redirected_to: str | None
    error: str | None
    sent_at: datetime | None
    created_at: datetime


class HistoryOut(BaseModel):
    from_status: str | None
    to_status: str
    reason: str
    actor: str
    created_at: datetime


class NoteOut(BaseModel):
    id: uuid.UUID
    body: str
    author_user_id: uuid.UUID | None
    created_at: datetime


class OutcomeOut(BaseModel):
    outcome: str
    value_egp: float | None
    reason: str | None
    created_at: datetime


class LeadDetailOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    score: int | None
    score_reasons: list[str]
    disqualify_reason: str | None
    category: str | None
    address: str | None
    city: str | None
    governorate: str | None
    website: str | None
    google_maps_url: str | None
    rating: float | None
    reviews_count: int | None
    agent_paused: bool
    icp_version_id: uuid.UUID | None
    sourcing_run_id: uuid.UUID | None
    next_action_at: datetime | None
    first_contacted_at: datetime | None
    last_outbound_at: datetime | None
    last_inbound_at: datetime | None
    created_at: datetime
    window_expires_at: datetime | None  # the 24h window; manual messages need it open
    contacts: list[ContactOut]
    messages: list[MessageOut]
    history: list[HistoryOut]
    notes: list[NoteOut]
    outcome: OutcomeOut | None


class LeadPatchIn(BaseModel):
    status: LeadStatus | None = None
    agent_paused: bool | None = None


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class OutcomeIn(BaseModel):
    outcome: Literal["won", "lost"]
    value_egp: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    reason: str | None = Field(default=None, max_length=2000)


class ContactIn(BaseModel):
    type: ContactType
    value: str = Field(min_length=1, max_length=500)


class ManualMessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4096)


class LeadFilters(BaseModel):
    """The list filters (CONTRACTS section 11 GET /leads); the export respects the same ones."""

    status: LeadStatus | None = None
    min_score: int | None = None
    q: str | None = None
    governorate: str | None = None
    sourcing_run_id: uuid.UUID | None = None


# ------------------------------------------------------------------------------------------------ helpers


async def get_lead(
    session: AsyncSession, tenant_id: uuid.UUID, lead_id: uuid.UUID, *, lock: bool = False
) -> Lead:
    stmt = select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    lead = (await session.execute(stmt)).scalar_one_or_none()
    if lead is None:
        raise NotFoundError("lead")
    return lead


def _ensure_not_opted_out(lead: Lead) -> None:
    if lead.status == LeadStatus.OPTED_OUT.value:
        raise AppError("opted_out", "This lead opted out; it cannot be changed or messaged.", status_code=409)


async def _set_status(
    session: AsyncSession, lead: Lead, to: LeadStatus, user_id: uuid.UUID, reason: str
) -> None:
    await lead_state.transition(
        session, lead, to, reason=reason, actor="user", actor_user_id=user_id, force=True
    )


def _num(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


# ------------------------------------------------------------------------------------------------ detail


async def lead_detail(session: AsyncSession, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> LeadDetailOut:
    lead = await get_lead(session, tenant_id, lead_id)
    scoped = {"tenant_id": tenant_id, "lead_id": lead_id}

    def where(model: Any) -> Any:
        return [model.tenant_id == scoped["tenant_id"], model.lead_id == scoped["lead_id"]]

    contacts = (
        await session.execute(
            select(Contact)
            .where(*where(Contact))
            .order_by(Contact.type, Contact.is_primary.desc(), Contact.value)
        )
    ).scalars()
    messages = (
        await session.execute(select(Message).where(*where(Message)).order_by(Message.created_at, Message.id))
    ).scalars()
    history = (
        await session.execute(
            select(LeadStatusHistory)
            .where(*where(LeadStatusHistory))
            .order_by(LeadStatusHistory.created_at, LeadStatusHistory.id)
        )
    ).scalars()
    notes = (
        await session.execute(select(LeadNote).where(*where(LeadNote)).order_by(LeadNote.created_at.desc()))
    ).scalars()
    outcome = (
        (
            await session.execute(
                select(LeadOutcome).where(*where(LeadOutcome)).order_by(LeadOutcome.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    window = await session.scalar(
        select(Conversation.window_expires_at)
        .where(*where(Conversation))
        .order_by(Conversation.window_expires_at.desc().nulls_last())
    )
    return LeadDetailOut(
        id=lead.id,
        name=lead.name,
        status=lead.status,
        score=lead.score,
        score_reasons=[str(r) for r in (lead.score_reasons or [])],
        disqualify_reason=lead.disqualify_reason,
        category=lead.category,
        address=lead.address,
        city=lead.city,
        governorate=lead.governorate,
        website=lead.website,
        google_maps_url=lead.google_maps_url,
        rating=lead.rating,
        reviews_count=lead.reviews_count,
        agent_paused=lead.agent_paused,
        icp_version_id=lead.icp_version_id,
        sourcing_run_id=lead.sourcing_run_id,
        next_action_at=lead.next_action_at,
        first_contacted_at=lead.first_contacted_at,
        last_outbound_at=lead.last_outbound_at,
        last_inbound_at=lead.last_inbound_at,
        created_at=lead.created_at,
        window_expires_at=window,
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
            MessageOut(
                id=m.id,
                direction=m.direction,
                author=m.author,
                kind=m.kind,
                purpose=m.purpose,
                status=m.status,
                body=m.body,
                template_name=m.template_name,
                reply_intent=m.reply_intent,
                redirected_to=messaging.mask(m.redirected_to) if m.redirected_to else None,
                error=m.error,
                sent_at=m.sent_at,
                created_at=m.created_at,
            )
            for m in messages
        ],
        history=[
            HistoryOut(
                from_status=h.from_status,
                to_status=h.to_status,
                reason=h.reason,
                actor=h.actor,
                created_at=h.created_at,
            )
            for h in history
        ],
        notes=[
            NoteOut(id=n.id, body=n.body, author_user_id=n.author_user_id, created_at=n.created_at)
            for n in notes
        ],
        outcome=(
            OutcomeOut(
                outcome=outcome.outcome,
                value_egp=_num(outcome.value_egp),
                reason=outcome.reason,
                created_at=outcome.created_at,
            )
            if outcome
            else None
        ),
    )


# ------------------------------------------------------------------------------------------------ actions


async def patch_lead(
    session: AsyncSession, tenant_id: uuid.UUID, lead_id: uuid.UUID, user_id: uuid.UUID, data: LeadPatchIn
) -> None:
    lead = await get_lead(session, tenant_id, lead_id, lock=True)
    if data.status is not None and data.status.value != lead.status:
        _ensure_not_opted_out(lead)
        await _set_status(session, lead, data.status, user_id, "manual")
    if data.agent_paused is not None and data.agent_paused != lead.agent_paused:
        lead.agent_paused = data.agent_paused
        session.add(  # a history note: the status stays the same
            LeadStatusHistory(
                tenant_id=tenant_id,
                lead_id=lead.id,
                from_status=lead.status,
                to_status=lead.status,
                reason="agent paused by the owner" if data.agent_paused else "agent resumed by the owner",
                actor="user",
                actor_user_id=user_id,
            )
        )
    await session.commit()


async def add_note(
    session: AsyncSession, tenant_id: uuid.UUID, lead_id: uuid.UUID, user_id: uuid.UUID, data: NoteIn
) -> NoteOut:
    await get_lead(session, tenant_id, lead_id)
    note = LeadNote(tenant_id=tenant_id, lead_id=lead_id, author_user_id=user_id, body=data.body.strip())
    session.add(note)
    await session.commit()
    return NoteOut(id=note.id, body=note.body, author_user_id=note.author_user_id, created_at=note.created_at)


async def record_outcome(
    session: AsyncSession, tenant_id: uuid.UUID, lead_id: uuid.UUID, user_id: uuid.UUID, data: OutcomeIn
) -> OutcomeOut:
    lead = await get_lead(session, tenant_id, lead_id, lock=True)
    existing = (
        (
            await session.execute(
                select(LeadOutcome).where(LeadOutcome.tenant_id == tenant_id, LeadOutcome.lead_id == lead_id)
            )
        )
        .scalars()
        .first()
    )
    if existing is None:
        existing = LeadOutcome(tenant_id=tenant_id, lead_id=lead_id, outcome=data.outcome)
        session.add(existing)
    existing.outcome = data.outcome
    existing.value_egp = data.value_egp if data.outcome == "won" else None
    existing.reason = data.reason
    await _set_status(session, lead, LeadStatus(data.outcome), user_id, f"marked {data.outcome}")
    lead.agent_paused = True
    lead.next_action_at = None
    await session.commit()
    await insights.on_outcome_recorded(session, tenant_id)  # after the commit (CONTRACTS section 9)
    return OutcomeOut(
        outcome=existing.outcome,
        value_egp=_num(existing.value_egp),
        reason=existing.reason,
        created_at=existing.created_at,
    )


async def add_contact(
    session: AsyncSession, tenant_id: uuid.UUID, lead_id: uuid.UUID, user_id: uuid.UUID, data: ContactIn
) -> ContactOut:
    lead = await get_lead(session, tenant_id, lead_id, lock=True)
    value = data.value.strip()
    if data.type in (ContactType.MOBILE, ContactType.LANDLINE):
        normalized = normalize_eg_phone(value)
        if normalized is None:
            raise AppError("invalid_phone", "This is not a valid Egyptian phone number.", status_code=422)
        if data.type == ContactType.MOBILE and not is_eg_mobile(normalized):
            raise AppError("not_a_mobile", "This number is a landline, not a mobile number.", status_code=422)
        value = normalized
    same_type = (Contact.tenant_id == tenant_id, Contact.lead_id == lead_id, Contact.type == data.type.value)
    if await session.scalar(
        select(func.count()).select_from(Contact).where(*same_type, Contact.value == value)
    ):
        raise AppError("contact_exists", "This lead already has this contact.", status_code=409)
    has_primary = await session.scalar(
        select(func.count()).select_from(Contact).where(*same_type, Contact.is_primary.is_(True))
    )
    contact = Contact(
        tenant_id=tenant_id,
        lead_id=lead_id,
        type=data.type.value,
        value=value,
        source="manual",
        is_primary=not has_primary,
        confidence=1.0,
    )
    try:
        async with session.begin_nested():  # a concurrent insert of the same contact (unique constraint)
            session.add(contact)
    except IntegrityError as exc:
        raise AppError("contact_exists", "This lead already has this contact.", status_code=409) from exc
    if data.type == ContactType.MOBILE and lead.status == LeadStatus.NO_CONTACT.value:
        await _set_status(session, lead, LeadStatus.ENRICHED, user_id, "mobile added manually")
        lead.next_action_at = datetime.now(UTC)  # the outreach tick picks it up
    await session.commit()
    return ContactOut(
        id=contact.id,
        type=contact.type,
        value=contact.value,
        source=contact.source,
        is_primary=contact.is_primary,
        confidence=contact.confidence,
    )


async def send_manual_message(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    lead_id: uuid.UUID,
    data: ManualMessageIn,
    *,
    now: datetime | None = None,
) -> MessageOut:
    now = now or datetime.now(UTC)
    lead = await get_lead(session, tenant_id, lead_id)
    _ensure_not_opted_out(lead)
    window = await session.scalar(
        select(func.max(Conversation.window_expires_at)).where(
            Conversation.tenant_id == tenant_id, Conversation.lead_id == lead_id
        )
    )
    if window is None or window <= now:
        raise AppError(
            "window_closed",
            "WhatsApp only allows free text within 24 hours of the lead's last message. "
            "Use a template instead.",
            status_code=409,
        )
    message = await messaging.create_outbound(
        session,
        tenant_id=tenant_id,
        lead_id=lead_id,
        purpose=OutreachPurpose.REPLY,
        kind=MessageKind.TEXT,
        body=data.body.strip(),
        author=MessageAuthor.HUMAN,
        needs_approval=False,
    )
    await session.commit()
    return MessageOut(
        id=message.id,
        direction=MessageDirection.OUTBOUND.value,
        author=message.author,
        kind=message.kind,
        purpose=message.purpose,
        status=message.status,
        body=message.body,
        template_name=None,
        reply_intent=None,
        redirected_to=None,
        error=message.error,
        sent_at=message.sent_at,
        created_at=message.created_at,
    )


# ------------------------------------------------------------------------------------------------ export

EXPORT_COLUMNS = [
    "Name",
    "Status",
    "Score",
    "Governorate",
    "City",
    "Category",
    "Primary mobile",
    "Website",
    "First contacted",
    "Last inbound",
    "Last intent",
    "Outcome",
    "Value (EGP)",
    "Notes",
]


async def export_rows(session: AsyncSession, tenant_id: uuid.UUID, filters: LeadFilters) -> list[list[Any]]:
    mobile = (
        select(Contact.value)
        .where(
            Contact.tenant_id == Lead.tenant_id,
            Contact.lead_id == Lead.id,
            Contact.type == ContactType.MOBILE.value,
        )
        .order_by(Contact.is_primary.desc(), Contact.confidence.desc())
        .limit(1)
        .scalar_subquery()
    )
    intent = (
        select(Message.reply_intent)
        .where(
            Message.tenant_id == Lead.tenant_id,
            Message.lead_id == Lead.id,
            Message.direction == MessageDirection.INBOUND.value,
            Message.reply_intent.is_not(None),
        )
        .order_by(Message.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    outcome = (
        select(LeadOutcome.outcome)
        .where(LeadOutcome.tenant_id == Lead.tenant_id, LeadOutcome.lead_id == Lead.id)
        .order_by(LeadOutcome.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    value = (
        select(LeadOutcome.value_egp)
        .where(LeadOutcome.tenant_id == Lead.tenant_id, LeadOutcome.lead_id == Lead.id)
        .order_by(LeadOutcome.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    notes = (
        select(func.count(LeadNote.id))
        .where(LeadNote.tenant_id == Lead.tenant_id, LeadNote.lead_id == Lead.id)
        .scalar_subquery()
    )
    stmt = select(
        Lead.name,
        Lead.status,
        Lead.score,
        Lead.governorate,
        Lead.city,
        Lead.category,
        mobile,
        Lead.website,
        Lead.first_contacted_at,
        Lead.last_inbound_at,
        intent,
        outcome,
        value,
        notes,
    ).where(Lead.tenant_id == tenant_id)
    if filters.status is not None:
        stmt = stmt.where(Lead.status == filters.status.value)
    if filters.min_score is not None:
        stmt = stmt.where(Lead.score >= filters.min_score)
    if filters.governorate:
        stmt = stmt.where(Lead.governorate == filters.governorate)
    if filters.sourcing_run_id is not None:
        stmt = stmt.where(Lead.sourcing_run_id == filters.sourcing_run_id)
    if filters.q:
        like = f"%{filters.q.strip()}%"
        stmt = stmt.where(or_(Lead.name.ilike(like), Lead.category.ilike(like), Lead.city.ilike(like)))
    stmt = stmt.order_by(Lead.score.desc().nulls_last(), Lead.created_at.desc())
    tz = ZoneInfo(app_settings.TIMEZONE)
    rows: list[list[Any]] = []
    for r in (await session.execute(stmt)).all():
        row = list(r)
        for i in (8, 9):  # Excel has no time zones: show Cairo local time
            if row[i] is not None:
                row[i] = row[i].astimezone(tz).replace(tzinfo=None)
        row[12] = _num(row[12])
        rows.append(row)
    return rows


def build_workbook(rows: list[list[Any]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Leads"
    ws.append(EXPORT_COLUMNS)
    for row in rows:
        ws.append(row)
    header_fill = PatternFill("solid", fgColor="1F4E78")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for col in (9, 10):
        for (cell,) in ws.iter_rows(min_row=2, min_col=col, max_col=col):
            cell.number_format = "yyyy-mm-dd hh:mm"
    for idx, title in enumerate(EXPORT_COLUMNS, start=1):
        letter = get_column_letter(idx)
        longest = max([len(title)] + [len(str(c.value)) for c in ws[letter][1:] if c.value is not None])
        ws.column_dimensions[letter].width = min(max(10, longest + 2), 60)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
