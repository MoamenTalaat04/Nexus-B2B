"""Learned insights: the feedback loop's data side (CONTRACTS section 9, P4-4).

get_active_insights(session, tenant_id) → list[str]   read by A's lead scorer (P2-3) and put in its prompt
compute_stats(session, tenant_id)       → dict         win/reply rates per segment, computed in code (no LLM)
save_version(...)                       → LearnedInsight (new active version; older ones deactivated)
on_outcome_recorded(session, tenant_id)                 enqueue job_feedback after every 3rd outcome
                                                        (A's POST /leads/{id}/outcome calls it after commit)

learned_insights.stats holds {"computed": <compute_stats output>, "icp_suggestions": [...], "caveats": [...],
"prompt_version": "feedback@1", "run_id": "<uuid>"}.
"""

import logging
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tracing import mask_phones
from app.models.enums import MessageDirection
from app.models.leads import Lead, LeadOutcome
from app.models.messaging import Message
from app.models.notifications import LearnedInsight
from app.models.tenants import Tenant

logger = logging.getLogger("app.services.insights")

MIN_OUTCOMES = 3
TRIGGER_EVERY = 3  # run the feedback job after every 3rd new outcome
MAX_EXAMPLES = 10


async def get_active_insights(session: AsyncSession, tenant_id: uuid.UUID) -> list[str]:
    """The active version's rules ([] when there is none or the owner deactivated it)."""
    row = await get_active(session, tenant_id)
    return [str(i) for i in (row.insights if row else [])]


async def get_active(session: AsyncSession, tenant_id: uuid.UUID) -> LearnedInsight | None:
    return (
        await session.execute(
            select(LearnedInsight).where(
                LearnedInsight.tenant_id == tenant_id, LearnedInsight.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()


async def list_versions(session: AsyncSession, tenant_id: uuid.UUID) -> list[LearnedInsight]:
    rows = await session.execute(
        select(LearnedInsight)
        .where(LearnedInsight.tenant_id == tenant_id)
        .order_by(LearnedInsight.version.desc())
    )
    return list(rows.scalars())


async def save_version(
    session: AsyncSession, tenant_id: uuid.UUID, *, insights: list[str], stats: dict[str, Any]
) -> LearnedInsight:
    """A new active version (caller's transaction); the previous active one is deactivated."""
    await session.execute(select(Tenant.id).where(Tenant.id == tenant_id).with_for_update())
    current = await session.scalar(
        select(func.coalesce(func.max(LearnedInsight.version), 0)).where(
            LearnedInsight.tenant_id == tenant_id
        )
    )
    await session.execute(
        update(LearnedInsight)
        .where(LearnedInsight.tenant_id == tenant_id, LearnedInsight.is_active.is_(True))
        .values(is_active=False)
    )
    row = LearnedInsight(
        tenant_id=tenant_id, version=int(current or 0) + 1, insights=insights, stats=stats, is_active=True
    )
    session.add(row)
    await session.flush()
    return row


async def deactivate(
    session: AsyncSession, tenant_id: uuid.UUID, insight_id: uuid.UUID
) -> LearnedInsight | None:
    row = (
        await session.execute(
            select(LearnedInsight).where(
                LearnedInsight.id == insight_id, LearnedInsight.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        row.is_active = False
        await session.flush()
    return row


async def outcomes_count(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    total = await session.scalar(
        select(func.count(func.distinct(LeadOutcome.lead_id))).where(LeadOutcome.tenant_id == tenant_id)
    )
    return int(total or 0)


async def on_outcome_recorded(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
    """Call after a won/lost outcome is committed: enqueues job_feedback on every 3rd outcome (True if so)."""
    count = await outcomes_count(session, tenant_id)
    if count < MIN_OUTCOMES or count % TRIGGER_EVERY != 0:
        return False
    from app.workers.queue import enqueue  # local: keeps this module importable without arq in scripts

    try:
        await enqueue(
            "job_feedback",
            tenant_id=str(tenant_id),
            trigger="chained",
            _job_id=f"feedback:{tenant_id}:{count}",
        )
    except Exception:
        logger.exception("could not enqueue job_feedback for tenant %s", tenant_id)
        return False
    return True


# ---------------------------------------------------------------------------------------------- stats


def score_band(score: int | None) -> str:
    if score is None:
        return "unscored"
    if score <= 3:
        return "0-3"
    if score <= 6:
        return "4-6"
    if score <= 8:
        return "7-8"
    return "9-10"


def rating_band(rating: float | None) -> str:
    if rating is None:
        return "no rating"
    if rating < 4.0:
        return "<4.0"
    if rating < 4.5:
        return "4.0-4.4"
    return "4.5+"


def reviews_band(reviews: int | None) -> str:
    if reviews is None:
        return "no reviews"
    if reviews < 10:
        return "0-9"
    if reviews < 50:
        return "10-49"
    if reviews < 200:
        return "50-199"
    return "200+"


@dataclass
class LeadFacts:
    lead_id: uuid.UUID
    name: str
    category: str | None
    governorate: str | None
    city: str | None
    score: int | None
    rating: float | None
    reviews: int | None
    has_website: bool
    contacted_at: datetime | None
    first_reply_at: datetime | None
    outcome: str | None
    value_egp: Decimal | None
    reason: str | None


SEGMENTS: dict[str, Callable[[LeadFacts], str]] = {
    "category": lambda f: f.category or "unknown",
    "governorate": lambda f: f.governorate or "unknown",
    "score_band": lambda f: score_band(f.score),
    "rating_band": lambda f: rating_band(f.rating),
    "reviews_band": lambda f: reviews_band(f.reviews),
    "website": lambda f: "has website" if f.has_website else "no website",
}


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


async def load_facts(session: AsyncSession, tenant_id: uuid.UUID) -> list[LeadFacts]:
    """Every lead that was contacted or has an outcome (latest outcome per lead), in three queries."""
    latest = (
        select(
            LeadOutcome.lead_id,
            LeadOutcome.outcome,
            LeadOutcome.value_egp,
            LeadOutcome.reason,
            func.row_number()
            .over(partition_by=LeadOutcome.lead_id, order_by=LeadOutcome.created_at.desc())
            .label("rn"),
        )
        .where(LeadOutcome.tenant_id == tenant_id)
        .subquery()
    )
    outcomes = {
        row.lead_id: row for row in (await session.execute(select(latest).where(latest.c.rn == 1))).all()
    }
    replies = dict(
        (
            await session.execute(
                select(Message.lead_id, func.min(Message.sent_at))
                .where(Message.tenant_id == tenant_id, Message.direction == MessageDirection.INBOUND.value)
                .group_by(Message.lead_id)
            )
        ).all()
    )
    leads = (
        await session.execute(
            select(Lead).where(
                Lead.tenant_id == tenant_id,
                or_(Lead.first_contacted_at.is_not(None), Lead.id.in_(list(outcomes))),
            )
        )
    ).scalars()
    facts: list[LeadFacts] = []
    for lead in leads:
        outcome = outcomes.get(lead.id)
        facts.append(
            LeadFacts(
                lead_id=lead.id,
                name=lead.name,
                category=lead.category,
                governorate=lead.governorate,
                city=lead.city,
                score=lead.score,
                rating=lead.rating,
                reviews=lead.reviews_count,
                has_website=bool(lead.website),
                contacted_at=lead.first_contacted_at,
                first_reply_at=replies.get(lead.id) or lead.last_inbound_at,
                outcome=outcome.outcome if outcome else None,
                value_egp=outcome.value_egp if outcome else None,
                reason=outcome.reason if outcome else None,
            )
        )
    return facts


def stats_from_facts(facts: list[LeadFacts]) -> dict[str, Any]:
    decided = [f for f in facts if f.outcome in ("won", "lost")]
    won = [f for f in decided if f.outcome == "won"]
    contacted = [f for f in facts if f.contacted_at is not None]
    segments: dict[str, list[dict[str, Any]]] = {}
    for segment, key in SEGMENTS.items():
        groups: dict[str, dict[str, int]] = defaultdict(
            lambda: {"won": 0, "lost": 0, "contacted": 0, "replied": 0}
        )
        for f in facts:
            g = groups[key(f)]
            if f.outcome == "won":
                g["won"] += 1
            elif f.outcome == "lost":
                g["lost"] += 1
            if f.contacted_at is not None:
                g["contacted"] += 1
                if f.first_reply_at is not None:
                    g["replied"] += 1
        rows = [
            {
                "value": value,
                "n": g["won"] + g["lost"],
                "won": g["won"],
                "lost": g["lost"],
                "win_rate": _rate(g["won"], g["won"] + g["lost"]),
                "contacted": g["contacted"],
                "replied": g["replied"],
                "reply_rate": _rate(g["replied"], g["contacted"]),
            }
            for value, g in groups.items()
        ]
        segments[segment] = sorted(rows, key=lambda r: (-r["n"], -r["contacted"], r["value"]))

    def avg_reply_hours(items: list[LeadFacts]) -> float | None:
        hours = [
            (f.first_reply_at - f.contacted_at).total_seconds() / 3600
            for f in items
            if f.contacted_at and f.first_reply_at and f.first_reply_at >= f.contacted_at
        ]
        return round(sum(hours) / len(hours), 1) if hours else None

    lost = [f for f in decided if f.outcome == "lost"]
    return {
        "outcomes": len(decided),
        "won": len(won),
        "lost": len(lost),
        "win_rate": _rate(len(won), len(decided)),
        "won_value_egp": float(sum((f.value_egp or Decimal(0)) for f in won)),
        "contacted": len(contacted),
        "replied": sum(1 for f in contacted if f.first_reply_at is not None),
        "reply_rate": _rate(sum(1 for f in contacted if f.first_reply_at is not None), len(contacted)),
        "avg_hours_to_reply": {"won": avg_reply_hours(won), "lost": avg_reply_hours(lost)},
        "segments": segments,
    }


def examples_from_facts(facts: list[LeadFacts], limit: int = MAX_EXAMPLES) -> list[dict[str, Any]]:
    """Short won/lost summaries for the prompt (no phones, no contact data), alternating won and lost."""
    won = [f for f in facts if f.outcome == "won"]
    lost = [f for f in facts if f.outcome == "lost"]
    picked: list[LeadFacts] = []
    while (won or lost) and len(picked) < limit:
        if won:
            picked.append(won.pop(0))
        if lost and len(picked) < limit:
            picked.append(lost.pop(0))
    return [
        {
            "outcome": f.outcome,
            "name": f.name[:80],
            "category": f.category,
            "governorate": f.governorate,
            "city": f.city,
            "score": f.score,
            "rating": f.rating,
            "reviews": f.reviews,
            "website": f.has_website,
            "value_egp": float(f.value_egp) if f.value_egp is not None else None,
            "reason": mask_phones(f.reason or "")[:200] or None,
        }
        for f in picked
    ]


async def compute_stats(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Any]:
    return stats_from_facts(await load_facts(session, tenant_id))
