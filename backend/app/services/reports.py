"""Reports & cost analytics (P4-3, CONTRACTS section 11 /reports). Pure SQL aggregates, tenant-scoped.

A range is a pair of calendar days in Africa/Cairo (`settings.TIMEZONE`), both inclusive:
[from 00:00, to+1 00:00). The default range is the last 30 days including today. "Previous period" is the
equal-length range right before.

Metric definitions (the UI shows these as tooltips; keep them in sync with METRIC_DEFINITIONS):
- sourced: leads created in the range.
- scored: sourced leads that have a score.
- qualified: scored leads that reached `qualified` or any later stage (by status or status history).
  qualified rate = qualified / scored.
- contactable rate: qualified leads that reached `enriched` (or later) / qualified.
- contacted: leads whose first_contacted_at is in the range.
- replied: contacted leads with at least one inbound message. reply rate = replied / contacted.
- positive: contacted leads whose status is (or passed through, per lead_status_history) interested,
  wants_offer, wants_management or won. positive reply rate = positive / contacted.
- lead response time: median minutes between our first outbound (first_contacted_at) and their first inbound,
  for the contacted leads that replied.
- our response time: median minutes between an inbound message (received in the range) and our next sent
  outbound to the same lead, split by author (agent vs human).
- win rate = won / (won + lost) over outcomes recorded in the range; pipeline value = the sum of value_egp
  for won.
- LLM cost = the sum of agent_runs.total_cost_usd for runs created in the range (an estimate at the paid list
  price, also on a free tier); cost per qualified lead = LLM cost / qualified; cost per positive reply =
  LLM cost / positive. cache hit ratio = cache_read_tokens / input tokens (agent_steps in the range).
- Segments: governorate, category, score band (0-3, 4-6, 7-8, 9-10, unscored), over the contacted leads.
"""

import uuid
from datetime import date, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.core.errors import AppError
from app.models.enums import LeadStatus

DEFAULT_DAYS = 30
MAX_DAYS = 366

SegmentBy = Literal["governorate", "category", "score_band"]
Metric = Literal["sourced", "contacted", "replies", "won"]

METRIC_DEFINITIONS: dict[str, str] = {
    "sourced": "Leads created in the range.",
    "scored": "Sourced leads that have a score.",
    "qualified": "Scored leads that reached 'qualified' or a later stage.",
    "qualified_rate": "Qualified / scored.",
    "contactable_rate": "Qualified leads that reached 'enriched' (a mobile number was found) / qualified.",
    "contacted": "Leads first contacted in the range.",
    "replied": "Contacted leads with at least one reply.",
    "reply_rate": "Replied / contacted.",
    "positive": "Contacted leads that became interested, wants offer, wants management or won.",
    "positive_reply_rate": "Positive / contacted.",
    "lead_response_minutes": "Median minutes from our first message to the lead's first reply.",
    "our_response_minutes_agent": "Median minutes from a lead's message to the agent's next sent message.",
    "our_response_minutes_human": "Median minutes from a lead's message to the owner's next sent message.",
    "won": "Deals marked won in the range.",
    "lost": "Deals marked lost in the range.",
    "win_rate": "Won / (won + lost).",
    "pipeline_value_egp": "Sum of the value of won deals (EGP).",
    "llm_cost_usd": "Estimated AI cost of all agent runs in the range (paid list price).",
    "cost_per_qualified_lead_usd": "AI cost / qualified leads.",
    "cost_per_positive_reply_usd": "AI cost / positive replies.",
    "cache_hit_ratio": "Cached input tokens / all input tokens.",
}

# Status sets (constants from the enum, inlined into SQL; never user input).
_LATER_THAN_QUALIFIED = [s.value for s in LeadStatus if s not in (LeadStatus.NEW, LeadStatus.DISQUALIFIED)]
_ENRICHED_OR_LATER = [
    s.value
    for s in LeadStatus
    if s not in (LeadStatus.NEW, LeadStatus.QUALIFIED, LeadStatus.DISQUALIFIED, LeadStatus.NO_CONTACT)
]
_POSITIVE = [
    LeadStatus.INTERESTED.value,
    LeadStatus.WANTS_OFFER.value,
    LeadStatus.WANTS_MANAGEMENT.value,
    LeadStatus.WON.value,
]
_WON = [LeadStatus.WON.value]


def _sql_list(values: list[str]) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def _reached(alias: str, statuses: list[str]) -> str:
    """SQL: the lead's status is in `statuses`, or its history shows it passed through one of them."""
    values = _sql_list(statuses)
    return (
        f"({alias}.status IN {values} OR EXISTS (SELECT 1 FROM lead_status_history h "
        f"WHERE h.tenant_id = {alias}.tenant_id AND h.lead_id = {alias}.id AND h.to_status IN {values}))"
    )


def _has_inbound(alias: str) -> str:
    return (
        f"EXISTS (SELECT 1 FROM messages m WHERE m.tenant_id = {alias}.tenant_id "
        f"AND m.lead_id = {alias}.id AND m.direction = 'inbound')"
    )


# ------------------------------------------------------------------------------------------------ ranges


class DateRange(BaseModel):
    from_date: date
    to_date: date

    @property
    def days(self) -> int:
        return (self.to_date - self.from_date).days + 1

    def bounds(self) -> tuple[datetime, datetime]:
        tz = ZoneInfo(app_settings.TIMEZONE)
        start = datetime.combine(self.from_date, time(0), tzinfo=tz)
        end = datetime.combine(self.to_date + timedelta(days=1), time(0), tzinfo=tz)
        return start, end

    def previous(self) -> "DateRange":
        return DateRange(
            from_date=self.from_date - timedelta(days=self.days),
            to_date=self.from_date - timedelta(days=1),
        )


def resolve_range(from_date: date | None, to_date: date | None, *, today: date | None = None) -> DateRange:
    """Fill the defaults (last 30 days, Cairo) and validate the range."""
    today = today or datetime.now(ZoneInfo(app_settings.TIMEZONE)).date()
    to_d = to_date or today
    from_d = from_date or (to_d - timedelta(days=DEFAULT_DAYS - 1))
    if from_d > to_d:
        raise AppError("invalid_range", "'from' must be on or before 'to'.", status_code=422)
    if (to_d - from_d).days + 1 > MAX_DAYS:
        raise AppError("range_too_long", f"The range can be at most {MAX_DAYS} days.", status_code=422)
    return DateRange(from_date=from_d, to_date=to_d)


def _params(tenant_id: uuid.UUID, rng: DateRange) -> dict[str, Any]:
    start, end = rng.bounds()
    return {"t": tenant_id, "start": start, "end": end, "tz": app_settings.TIMEZONE}


def _rate(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or not denominator:
        return None
    return round(float(numerator) / float(denominator), 4)


def _num(value: Any, digits: int = 2) -> float | None:
    return None if value is None else round(float(value), digits)


# ------------------------------------------------------------------------------------------------ summary

_KPI_SQL = f"""
WITH sourced AS (
    SELECT l.* FROM leads l WHERE l.tenant_id = :t AND l.created_at >= :start AND l.created_at < :end
), contacted AS (
    SELECT l.* FROM leads l
    WHERE l.tenant_id = :t AND l.first_contacted_at >= :start AND l.first_contacted_at < :end
), qualified AS (
    SELECT s.* FROM sourced s WHERE s.score IS NOT NULL AND {_reached("s", _LATER_THAN_QUALIFIED)}
), first_replies AS (
    SELECT EXTRACT(EPOCH FROM (fi.at - c.first_contacted_at)) / 60.0 AS minutes
    FROM contacted c
    CROSS JOIN LATERAL (
        SELECT min(m.created_at) AS at FROM messages m
        WHERE m.tenant_id = :t AND m.lead_id = c.id AND m.direction = 'inbound'
          AND m.created_at >= c.first_contacted_at
    ) fi
    WHERE fi.at IS NOT NULL
)
SELECT
    (SELECT count(*) FROM sourced) AS sourced,
    (SELECT count(*) FROM sourced WHERE score IS NOT NULL) AS scored,
    (SELECT count(*) FROM qualified) AS qualified,
    (SELECT count(*) FROM qualified q WHERE {_reached("q", _ENRICHED_OR_LATER)}) AS contactable,
    (SELECT count(*) FROM contacted) AS contacted,
    (SELECT count(*) FROM contacted c WHERE {_has_inbound("c")}) AS replied,
    (SELECT count(*) FROM contacted c WHERE {_reached("c", _POSITIVE)}) AS positive,
    (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY minutes) FROM first_replies) AS lead_response_minutes,
    (SELECT count(*) FROM lead_outcomes o WHERE o.tenant_id = :t AND o.outcome = 'won'
        AND o.created_at >= :start AND o.created_at < :end) AS won,
    (SELECT count(*) FROM lead_outcomes o WHERE o.tenant_id = :t AND o.outcome = 'lost'
        AND o.created_at >= :start AND o.created_at < :end) AS lost,
    (SELECT coalesce(sum(o.value_egp), 0) FROM lead_outcomes o WHERE o.tenant_id = :t AND o.outcome = 'won'
        AND o.created_at >= :start AND o.created_at < :end) AS pipeline_value_egp,
    (SELECT coalesce(sum(r.total_cost_usd), 0) FROM agent_runs r WHERE r.tenant_id = :t
        AND r.created_at >= :start AND r.created_at < :end) AS llm_cost_usd,
    (SELECT coalesce(sum(st.input_tokens), 0) FROM agent_steps st WHERE st.tenant_id = :t
        AND st.created_at >= :start AND st.created_at < :end) AS input_tokens,
    (SELECT coalesce(sum(st.cache_read_tokens), 0) FROM agent_steps st WHERE st.tenant_id = :t
        AND st.created_at >= :start AND st.created_at < :end) AS cache_read_tokens
"""

_OUR_RESPONSE_SQL = """
SELECT nxt.author, percentile_cont(0.5) WITHIN GROUP (
    ORDER BY EXTRACT(EPOCH FROM (nxt.sent_at - i.created_at)) / 60.0) AS minutes
FROM messages i
CROSS JOIN LATERAL (
    SELECT o.author, o.sent_at FROM messages o
    WHERE o.tenant_id = :t AND o.lead_id = i.lead_id AND o.direction = 'outbound'
      AND o.sent_at IS NOT NULL AND o.sent_at > i.created_at
    ORDER BY o.sent_at LIMIT 1
) nxt
WHERE i.tenant_id = :t AND i.direction = 'inbound' AND i.created_at >= :start AND i.created_at < :end
GROUP BY nxt.author
"""


async def compute_kpis(
    session: AsyncSession, tenant_id: uuid.UUID, rng: DateRange
) -> dict[str, float | None]:
    """Every KPI for one range (see the module docstring for the definitions)."""
    params = _params(tenant_id, rng)
    row = (await session.execute(text(_KPI_SQL), params)).mappings().one()
    response = {
        r["author"]: r["minutes"] for r in (await session.execute(text(_OUR_RESPONSE_SQL), params)).mappings()
    }
    cost = float(row["llm_cost_usd"])
    won, lost = int(row["won"]), int(row["lost"])
    return {
        "sourced": int(row["sourced"]),
        "scored": int(row["scored"]),
        "qualified": int(row["qualified"]),
        "qualified_rate": _rate(row["qualified"], row["scored"]),
        "contactable_rate": _rate(row["contactable"], row["qualified"]),
        "contacted": int(row["contacted"]),
        "replied": int(row["replied"]),
        "reply_rate": _rate(row["replied"], row["contacted"]),
        "positive": int(row["positive"]),
        "positive_reply_rate": _rate(row["positive"], row["contacted"]),
        "lead_response_minutes": _num(row["lead_response_minutes"], 1),
        "our_response_minutes_agent": _num(response.get("agent"), 1),
        "our_response_minutes_human": _num(response.get("human"), 1),
        "won": won,
        "lost": lost,
        "win_rate": _rate(won, won + lost),
        "pipeline_value_egp": _num(row["pipeline_value_egp"]),
        "llm_cost_usd": round(cost, 6),
        "cost_per_qualified_lead_usd": _rate(cost, row["qualified"]) if cost else None,
        "cost_per_positive_reply_usd": _rate(cost, row["positive"]) if cost else None,
        "cache_hit_ratio": _rate(row["cache_read_tokens"], row["input_tokens"]),
    }


class Kpi(BaseModel):
    value: int | float | None
    previous: int | float | None
    delta: float | None
    definition: str


class SummaryOut(BaseModel):
    from_date: date
    to_date: date
    previous_from: date
    previous_to: date
    cost_is_estimated: bool = True
    kpis: dict[str, Kpi]


async def summary(session: AsyncSession, tenant_id: uuid.UUID, rng: DateRange) -> SummaryOut:
    current = await compute_kpis(session, tenant_id, rng)
    prev_rng = rng.previous()
    previous = await compute_kpis(session, tenant_id, prev_rng)
    kpis = {}
    for name, value in current.items():
        before = previous[name]
        delta = None if value is None or before is None else round(float(value) - float(before), 6)
        kpis[name] = Kpi(value=value, previous=before, delta=delta, definition=METRIC_DEFINITIONS[name])
    return SummaryOut(
        from_date=rng.from_date,
        to_date=rng.to_date,
        previous_from=prev_rng.from_date,
        previous_to=prev_rng.to_date,
        kpis=kpis,
    )


# ------------------------------------------------------------------------------------------------ funnel

FUNNEL_STAGES = ["sourced", "qualified", "contacted", "replied", "positive", "won"]

_FUNNEL_SQL = f"""
SELECT
    count(*) AS sourced,
    count(*) FILTER (WHERE {_reached("l", _LATER_THAN_QUALIFIED)}) AS qualified,
    count(*) FILTER (WHERE l.first_contacted_at IS NOT NULL) AS contacted,
    count(*) FILTER (WHERE l.first_contacted_at IS NOT NULL AND {_has_inbound("l")}) AS replied,
    count(*) FILTER (WHERE l.first_contacted_at IS NOT NULL AND {_reached("l", _POSITIVE)}) AS positive,
    count(*) FILTER (WHERE {_reached("l", _WON)}) AS won
FROM leads l
WHERE l.tenant_id = :t AND l.created_at >= :start AND l.created_at < :end
"""


class FunnelStage(BaseModel):
    stage: str
    count: int
    rate_from_previous: float | None  # this stage / the stage before (None for the first)


class FunnelOut(BaseModel):
    from_date: date
    to_date: date
    cohort: str = "leads sourced in the range"
    stages: list[FunnelStage]


async def funnel(session: AsyncSession, tenant_id: uuid.UUID, rng: DateRange) -> FunnelOut:
    """The leads sourced in the range, and how many of them reached each later stage."""
    row = (await session.execute(text(_FUNNEL_SQL), _params(tenant_id, rng))).mappings().one()
    stages: list[FunnelStage] = []
    for i, name in enumerate(FUNNEL_STAGES):
        count = int(row[name])
        prev = stages[i - 1].count if i else None
        stages.append(
            FunnelStage(stage=name, count=count, rate_from_previous=_rate(count, prev) if i else None)
        )
    return FunnelOut(from_date=rng.from_date, to_date=rng.to_date, stages=stages)


# ------------------------------------------------------------------------------------------------ segments

_SEGMENT_EXPR: dict[str, str] = {
    "governorate": "coalesce(nullif(l.governorate, ''), 'unknown')",
    "category": "coalesce(nullif(l.category, ''), 'unknown')",
    "score_band": (
        "CASE WHEN l.score IS NULL THEN 'unscored' WHEN l.score <= 3 THEN '0-3' WHEN l.score <= 6 THEN '4-6' "
        "WHEN l.score <= 8 THEN '7-8' ELSE '9-10' END"
    ),
}


class SegmentRow(BaseModel):
    segment: str
    contacted: int
    replied: int
    positive: int
    won: int
    reply_rate: float | None
    positive_reply_rate: float | None


class SegmentsOut(BaseModel):
    from_date: date
    to_date: date
    by: str
    cohort: str = "leads first contacted in the range"
    rows: list[SegmentRow]


async def segments(session: AsyncSession, tenant_id: uuid.UUID, rng: DateRange, by: SegmentBy) -> SegmentsOut:
    expr = _SEGMENT_EXPR[by]  # `by` is a validated Literal, never free text
    sql = f"""
    SELECT {expr} AS segment,
        count(*) AS contacted,
        count(*) FILTER (WHERE {_has_inbound("l")}) AS replied,
        count(*) FILTER (WHERE {_reached("l", _POSITIVE)}) AS positive,
        count(*) FILTER (WHERE {_reached("l", _WON)}) AS won
    FROM leads l
    WHERE l.tenant_id = :t AND l.first_contacted_at >= :start AND l.first_contacted_at < :end
    GROUP BY 1
    ORDER BY contacted DESC, segment
    """
    rows = (await session.execute(text(sql), _params(tenant_id, rng))).mappings().all()
    return SegmentsOut(
        from_date=rng.from_date,
        to_date=rng.to_date,
        by=by,
        rows=[
            SegmentRow(
                segment=str(r["segment"]),
                contacted=int(r["contacted"]),
                replied=int(r["replied"]),
                positive=int(r["positive"]),
                won=int(r["won"]),
                reply_rate=_rate(r["replied"], r["contacted"]),
                positive_reply_rate=_rate(r["positive"], r["contacted"]),
            )
            for r in rows
        ],
    )


# ------------------------------------------------------------------------------------------------ costs

_COST_DAILY_SQL = """
SELECT (r.created_at AT TIME ZONE :tz)::date AS day, r.kind, count(*) AS runs,
       coalesce(sum(r.total_cost_usd), 0) AS cost_usd
FROM agent_runs r
WHERE r.tenant_id = :t AND r.created_at >= :start AND r.created_at < :end
GROUP BY 1, 2
ORDER BY 1, 2
"""

_COST_MODELS_SQL = """
SELECT st.model, count(*) AS calls, coalesce(sum(st.input_tokens), 0) AS input_tokens,
       coalesce(sum(st.output_tokens), 0) AS output_tokens,
       coalesce(sum(st.cache_read_tokens), 0) AS cache_read_tokens, coalesce(sum(st.cost_usd), 0) AS cost_usd
FROM agent_steps st
WHERE st.tenant_id = :t AND st.model IS NOT NULL AND st.created_at >= :start AND st.created_at < :end
GROUP BY st.model
ORDER BY cost_usd DESC, st.model
"""


class CostDay(BaseModel):
    day: date
    kind: str
    runs: int
    cost_usd: float


class CostByKind(BaseModel):
    kind: str
    runs: int
    cost_usd: float


class ModelUsage(BaseModel):
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_hit_ratio: float | None
    cost_usd: float


class CostsOut(BaseModel):
    from_date: date
    to_date: date
    cost_is_estimated: bool = True
    total_cost_usd: float
    cost_per_qualified_lead_usd: float | None
    cost_per_positive_reply_usd: float | None
    cache_hit_ratio: float | None
    by_kind: list[CostByKind]
    daily: list[CostDay]
    models: list[ModelUsage]


async def costs(session: AsyncSession, tenant_id: uuid.UUID, rng: DateRange) -> CostsOut:
    params = _params(tenant_id, rng)
    daily_rows = (await session.execute(text(_COST_DAILY_SQL), params)).mappings().all()
    model_rows = (await session.execute(text(_COST_MODELS_SQL), params)).mappings().all()
    kpis = await compute_kpis(session, tenant_id, rng)
    by_kind: dict[str, CostByKind] = {}
    for r in daily_rows:
        item = by_kind.setdefault(r["kind"], CostByKind(kind=r["kind"], runs=0, cost_usd=0.0))
        item.runs += int(r["runs"])
        item.cost_usd = round(item.cost_usd + float(r["cost_usd"]), 6)
    return CostsOut(
        from_date=rng.from_date,
        to_date=rng.to_date,
        total_cost_usd=float(kpis["llm_cost_usd"] or 0),
        cost_per_qualified_lead_usd=kpis["cost_per_qualified_lead_usd"],
        cost_per_positive_reply_usd=kpis["cost_per_positive_reply_usd"],
        cache_hit_ratio=kpis["cache_hit_ratio"],
        by_kind=sorted(by_kind.values(), key=lambda k: (-k.cost_usd, k.kind)),
        daily=[
            CostDay(
                day=r["day"], kind=r["kind"], runs=int(r["runs"]), cost_usd=round(float(r["cost_usd"]), 6)
            )
            for r in daily_rows
        ],
        models=[
            ModelUsage(
                model=r["model"],
                calls=int(r["calls"]),
                input_tokens=int(r["input_tokens"]),
                output_tokens=int(r["output_tokens"]),
                cache_read_tokens=int(r["cache_read_tokens"]),
                cache_hit_ratio=_rate(r["cache_read_tokens"], r["input_tokens"]),
                cost_usd=round(float(r["cost_usd"]), 6),
            )
            for r in model_rows
        ],
    )


# ------------------------------------------------------------------------------------------------ timeseries

_SERIES_SOURCE: dict[str, str] = {
    "sourced": "SELECT created_at AS at FROM leads WHERE tenant_id = :t",
    "contacted": (
        "SELECT first_contacted_at AS at FROM leads WHERE tenant_id = :t AND first_contacted_at IS NOT NULL"
    ),
    "replies": "SELECT created_at AS at FROM messages WHERE tenant_id = :t AND direction = 'inbound'",
    "won": "SELECT created_at AS at FROM lead_outcomes WHERE tenant_id = :t AND outcome = 'won'",
}


class SeriesPoint(BaseModel):
    day: date
    value: int


class TimeseriesOut(BaseModel):
    from_date: date
    to_date: date
    metric: str
    points: list[SeriesPoint]


async def timeseries(
    session: AsyncSession, tenant_id: uuid.UUID, rng: DateRange, metric: Metric
) -> TimeseriesOut:
    """Daily counts (Cairo days), one point per day of the range, zero-filled."""
    source = _SERIES_SOURCE[metric]  # validated Literal
    sql = f"""
    WITH events AS ({source} AND {"first_contacted_at" if metric == "contacted" else "created_at"} >= :start
                     AND {"first_contacted_at" if metric == "contacted" else "created_at"} < :end),
         days AS (SELECT generate_series(CAST(:d0 AS date), CAST(:d1 AS date), interval '1 day')::date AS day)
    SELECT d.day, count(e.at) AS value
    FROM days d LEFT JOIN events e ON (e.at AT TIME ZONE :tz)::date = d.day
    GROUP BY d.day ORDER BY d.day
    """
    params = {**_params(tenant_id, rng), "d0": rng.from_date, "d1": rng.to_date}
    rows = (await session.execute(text(sql), params)).mappings().all()
    return TimeseriesOut(
        from_date=rng.from_date,
        to_date=rng.to_date,
        metric=metric,
        points=[SeriesPoint(day=r["day"], value=int(r["value"])) for r in rows],
    )
