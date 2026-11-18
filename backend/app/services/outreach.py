"""Outreach engine (P3-3): who gets messaged, when, and with what.

tick_tenant() runs every 5 minutes per tenant with the agent enabled (job_outreach_tick):
1. Only on working days and inside the sending window (quiet_hours_start..quiet_hours_end, Africa/Cairo).
2. Remaining daily cap = daily_send_cap - first touches/follow-ups created today (rejected/blocked/failed
   don't count).
3. Due leads: next_action_at <= now (or newly enriched leads with no date yet), not paused, status enriched /
   contacted / later, never opted_out; oldest first, at most the remaining cap, locked with SKIP LOCKED so two
   ticks never take the same lead. A lead that already has an open message (waiting for approval, queued or
   waiting for the owner to send) is skipped, so a lead never gets two messages.
4. Per lead, the step comes from settings.sequence_steps and lead.sequence_step:
   - enriched → first touch, ENRICHED→QUEUED;
   - contacted with no reply since our last message → the next follow-up, if any; none left → sequence done;
   - later (when due) → a follow-up; LATER→CONTACTED once it is sent.
5. The message: first_touch_mode="assisted" → a personal text the owner sends (kind=ASSISTED);
   "api_template" → an approved template with personalized params (kind=TEMPLATE), approval per autonomy mode.
   No approved template for the step → the owner is notified once (channel_error) and the lead is skipped.
One OUTREACH_TICK agent_run per tenant per tick, only when there is work.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm.base import LLMProviderError
from app.agents import message_personalizer as personalizer
from app.agents.llm import LLMInvalidOutput, LLMOutputTruncated, LLMRefused
from app.config import settings as app_settings
from app.core import lead_state
from app.core.tracing import RunContext, agent_run
from app.models.enums import (
    AgentRunKind,
    ChannelType,
    FirstTouchMode,
    LeadStatus,
    MessageDirection,
    MessageKind,
    MessageStatus,
    OutreachPurpose,
    StepType,
)
from app.models.leads import Lead
from app.models.messaging import Message, MessageTemplate
from app.models.notifications import Notification
from app.models.tenants import BusinessSettings
from app.schemas.agent_io import ICP, CompanyProfile
from app.services import icp_service, messaging
from app.services.autonomy import needs_approval
from app.services.notifications import notify_owner

logger = logging.getLogger("app.services.outreach")

DUE_STATUSES = (LeadStatus.ENRICHED.value, LeadStatus.CONTACTED.value, LeadStatus.LATER.value)
OPEN_STATUSES = (
    MessageStatus.PENDING_APPROVAL.value,
    MessageStatus.APPROVED.value,
    MessageStatus.QUEUED.value,
    MessageStatus.AWAITING_MANUAL_SEND.value,
)
NOT_COUNTED = (MessageStatus.REJECTED.value, MessageStatus.BLOCKED.value, MessageStatus.FAILED.value)
CAPPED_PURPOSES = (OutreachPurpose.FIRST_TOUCH.value, OutreachPurpose.FOLLOWUP.value)
LLM_ERRORS = (LLMRefused, LLMOutputTruncated, LLMInvalidOutput, LLMProviderError)


def local_tz() -> ZoneInfo:
    return ZoneInfo(app_settings.TIMEZONE)


@dataclass
class TickResult:
    tenant_id: uuid.UUID
    created: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    reason: str | None = None  # why nothing ran (outside_hours, cap_reached, no_due_leads, no_icp)
    run_id: uuid.UUID | None = None

    def skip(self, why: str) -> None:
        self.skipped[why] = self.skipped.get(why, 0) + 1


# ---------------------------------------------------------------------------------------------- rules


def in_sending_window(settings: BusinessSettings, now: datetime) -> bool:
    local = now.astimezone(local_tz())
    if local.weekday() not in (settings.working_days or []):
        return False
    return settings.quiet_hours_start <= local.time().replace(tzinfo=None) < settings.quiet_hours_end


def start_of_local_day(now: datetime) -> datetime:
    local = now.astimezone(local_tz())
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


async def counted_today(session: AsyncSession, tenant_id: uuid.UUID, now: datetime) -> int:
    """First touches + follow-ups created today (Cairo day) that count against the daily cap."""
    total = await session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.tenant_id == tenant_id,
            Message.direction == MessageDirection.OUTBOUND.value,
            Message.purpose.in_(CAPPED_PURPOSES),
            Message.status.not_in(NOT_COUNTED),
            Message.created_at >= start_of_local_day(now),
        )
    )
    return int(total or 0)


async def sent_today(session: AsyncSession, tenant_id: uuid.UUID, now: datetime) -> int:
    """First touches + follow-ups actually sent today (for "7 of 15 sent today")."""
    total = await session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.tenant_id == tenant_id,
            Message.direction == MessageDirection.OUTBOUND.value,
            Message.purpose.in_(CAPPED_PURPOSES),
            Message.sent_at.is_not(None),
            Message.sent_at >= start_of_local_day(now),
        )
    )
    return int(total or 0)


async def due_leads(session: AsyncSession, tenant_id: uuid.UUID, now: datetime, limit: int) -> list[Lead]:
    rows = await session.execute(
        select(Lead)
        .where(
            Lead.tenant_id == tenant_id,
            Lead.agent_paused.is_(False),
            Lead.status.in_(DUE_STATUSES),
            or_(
                Lead.next_action_at <= now,
                and_(Lead.status == LeadStatus.ENRICHED.value, Lead.next_action_at.is_(None)),
            ),
        )
        .order_by(Lead.next_action_at.asc().nulls_first(), Lead.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(rows.scalars())


async def _has_open_message(session: AsyncSession, lead: Lead) -> bool:
    found = await session.scalar(
        select(Message.id)
        .where(
            Message.tenant_id == lead.tenant_id,
            Message.lead_id == lead.id,
            Message.direction == MessageDirection.OUTBOUND.value,
            Message.status.in_(OPEN_STATUSES),
        )
        .limit(1)
    )
    return found is not None


def _steps(settings: BusinessSettings) -> list[dict[str, Any]]:
    return sorted(settings.sequence_steps or [], key=lambda s: int(s.get("day_offset", 0)))


async def _approved_template(
    session: AsyncSession, tenant_id: uuid.UUID, purpose: str
) -> MessageTemplate | None:
    return (
        await session.execute(
            select(MessageTemplate)
            .where(
                MessageTemplate.tenant_id == tenant_id,
                MessageTemplate.channel == ChannelType.WHATSAPP.value,
                MessageTemplate.purpose == purpose,
                MessageTemplate.status == "approved",
            )
            .order_by(MessageTemplate.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()


async def _notify_once(session: AsyncSession, tenant_id: uuid.UUID, title: str, body: str) -> None:
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


# ---------------------------------------------------------------------------------------------- the tick


@dataclass
class _Context:
    session: AsyncSession
    settings: BusinessSettings
    profile: CompanyProfile
    icp: ICP
    steps: list[dict[str, Any]]
    connection: Any
    now: datetime
    run: RunContext
    result: TickResult


async def tick_tenant(session: AsyncSession, settings: BusinessSettings, *, now: datetime) -> TickResult:
    """One outreach pass for one tenant. Commits its work; row locks end with the caller's session."""
    result = TickResult(settings.tenant_id)
    if not in_sending_window(settings, now):
        result.reason = "outside_hours"
        return result
    remaining = settings.daily_send_cap - await counted_today(session, settings.tenant_id, now)
    if remaining <= 0:
        result.reason = "cap_reached"
        return result
    leads = await due_leads(session, settings.tenant_id, now, remaining)
    if not leads:
        result.reason = "no_due_leads"
        return result
    active = await icp_service.get_active_icp(session, settings.tenant_id)
    if active is None:
        result.reason = "no_icp"
        return result

    async with agent_run(
        settings.tenant_id,
        AgentRunKind.OUTREACH_TICK,
        trigger="schedule",
        input={"due_leads": len(leads), "remaining_cap": remaining, "mode": settings.first_touch_mode},
    ) as run:
        result.run_id = run.run_id
        ctx = _Context(
            session=session,
            settings=settings,
            profile=CompanyProfile.model_validate(active.company_profile),
            icp=ICP.model_validate(active.icp),
            steps=_steps(settings),
            connection=await messaging.get_whatsapp_connection(session, settings.tenant_id),
            now=now,
            run=run,
            result=result,
        )
        for lead in leads:
            try:
                await _process_lead(ctx, lead)
            except LLM_ERRORS as exc:
                result.skip("ai_error")
                await run.step(
                    StepType.ERROR, "outreach.ai_error", output={"error": str(exc)}, lead_id=lead.id
                )
        run.output_summary = {"created": result.created, "skipped": result.skipped}
        await session.commit()
    return result


async def _process_lead(ctx: _Context, lead: Lead) -> None:
    session, result = ctx.session, ctx.result
    if await _has_open_message(session, lead):
        result.skip("has_open_message")
        return
    status = LeadStatus(lead.status)
    if (
        status == LeadStatus.CONTACTED
        and lead.last_inbound_at
        and (lead.last_outbound_at is None or lead.last_inbound_at > lead.last_outbound_at)
    ):
        lead.next_action_at = None  # they replied; the reply agent takes over
        result.skip("replied")
        return

    index = lead.sequence_step
    if status == LeadStatus.LATER:
        step = next((s for s in ctx.steps if s.get("purpose") == OutreachPurpose.FOLLOWUP.value), None)
        if step is None:
            lead.next_action_at = None
            result.skip("no_followup_step")
            return
    else:
        if index >= len(ctx.steps):
            lead.next_action_at = None
            result.skip("sequence_finished")
            return
        step = ctx.steps[index]
    purpose = OutreachPurpose(step.get("purpose", OutreachPurpose.FOLLOWUP.value))
    if status == LeadStatus.ENRICHED and purpose != OutreachPurpose.FIRST_TOUCH:
        result.skip("bad_sequence")
        return
    if status == LeadStatus.CONTACTED and purpose == OutreachPurpose.FIRST_TOUCH:
        result.skip("bad_sequence")
        return

    message, rationale = await _create_message(ctx, lead, step, purpose)
    if message is None:
        return
    if message.status == MessageStatus.BLOCKED.value:
        result.skip("blocked")
        return
    await ctx.run.step(
        StepType.DECISION,
        "outreach.message",
        output={
            "message_id": str(message.id),
            "purpose": purpose.value,
            "kind": message.kind,
            "status": message.status,
            "rationale": rationale,
            "preview": message.body,
        },
        lead_id=lead.id,
    )
    if status == LeadStatus.ENRICHED:
        await lead_state.transition(
            session, lead, LeadStatus.QUEUED, reason="first touch prepared", actor="agent"
        )
    if status == LeadStatus.LATER:
        lead.next_action_at = None  # LATER→CONTACTED happens when the follow-up is sent
    else:
        lead.sequence_step = index + 1
        following = ctx.steps[index + 1] if index + 1 < len(ctx.steps) else None
        gap = int(following.get("day_offset", 0)) - int(step.get("day_offset", 0)) if following else None
        lead.next_action_at = ctx.now + timedelta(days=max(gap, 1)) if gap is not None else None
    result.created += 1


async def _create_message(
    ctx: _Context, lead: Lead, step: dict[str, Any], purpose: OutreachPurpose
) -> tuple[Message | None, str]:
    session, settings = ctx.session, ctx.settings
    if settings.first_touch_mode == FirstTouchMode.ASSISTED.value:
        link = messaging.assistant_link(settings, ctx.connection, lead)
        assisted = await personalizer.write_assisted(
            ctx.run, profile=ctx.profile, icp=ctx.icp, lead=lead, step_purpose=purpose, assistant_link=link
        )
        message = await messaging.create_outbound(
            session,
            tenant_id=lead.tenant_id,
            lead_id=lead.id,
            purpose=purpose,
            kind=MessageKind.ASSISTED,
            body=assisted.text,
            needs_approval=False,
            agent_run_id=ctx.run.run_id,
        )
        return message, assisted.rationale

    template_purpose = str(
        step.get("template") or ("intro" if purpose == OutreachPurpose.FIRST_TOUCH else "followup")
    )
    template = await _approved_template(session, lead.tenant_id, template_purpose)
    if template is None:
        await _notify_once(
            session,
            lead.tenant_id,
            title=f"No approved WhatsApp template for '{template_purpose}'",
            body="The agent cannot message leads until a template with this purpose is approved by Meta and "
            "tagged in Settings → Channels.",
        )
        ctx.result.skip("missing_template")
        return None, ""
    opening = await personalizer.personalize(
        ctx.run, profile=ctx.profile, icp=ctx.icp, lead=lead, template=template, step_purpose=purpose
    )
    message = await messaging.create_outbound(
        session,
        tenant_id=lead.tenant_id,
        lead_id=lead.id,
        purpose=purpose,
        kind=MessageKind.TEMPLATE,
        body=opening.preview_text,
        template_name=template.name,
        template_params=opening.template_params,
        needs_approval=needs_approval(settings, purpose),
        agent_run_id=ctx.run.run_id,
    )
    return message, opening.rationale


# ---------------------------------------------------------------------------------------------- hooks


async def on_message_sent(session: AsyncSession, message: Message) -> None:
    """Called by messaging when a first touch / follow-up becomes sent: QUEUED or LATER → CONTACTED."""
    if message.direction != MessageDirection.OUTBOUND.value or message.purpose not in CAPPED_PURPOSES:
        return
    lead = await session.get(Lead, message.lead_id)
    if lead is None:
        return
    if lead.status in (LeadStatus.QUEUED.value, LeadStatus.LATER.value):
        await lead_state.transition(
            session, lead, LeadStatus.CONTACTED, reason="message sent", actor="system"
        )


async def reject(
    session: AsyncSession, *, tenant_id: uuid.UUID, message_id: uuid.UUID, user_id: uuid.UUID
) -> Message:
    """The owner decided not to contact this lead now: reject the message and pause the agent for the lead."""
    message = await messaging.reject_message(
        session, tenant_id=tenant_id, message_id=message_id, user_id=user_id
    )
    lead = await session.get(Lead, message.lead_id)
    if lead is not None:
        if lead.status == LeadStatus.QUEUED.value:
            await lead_state.transition(
                session,
                lead,
                LeadStatus.ENRICHED,
                reason="first message rejected",
                actor="user",
                actor_user_id=user_id,
            )
        lead.sequence_step = max(0, lead.sequence_step - 1)  # the same step runs again if the owner resumes
        lead.agent_paused = True
        await session.flush()
    return message
