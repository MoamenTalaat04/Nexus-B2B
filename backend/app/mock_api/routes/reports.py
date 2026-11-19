"""Mock Reports & Insights routes: /reports/* and /insights/*."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query

from app.core.errors import AppError, NotFoundError
from app.core.security import CurrentUser
from app.mock_api.helpers import get_mock_current_user
from app.mock_api.state import MockAgentRun, MockLearnedInsight, get_store
from app.models.enums import AgentRunKind, AgentRunStatus, LeadStatus, MessageDirection

router = APIRouter(tags=["reports-and-insights"])

POSITIVE_STATUSES = {
    LeadStatus.INTERESTED.value,
    LeadStatus.WANTS_OFFER.value,
    LeadStatus.WANTS_MANAGEMENT.value,
    LeadStatus.WON.value,
}


@router.get("/reports/summary")
async def reports_summary(
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> dict[str, Any]:
    store = get_store()
    tid = current_user.tenant_id
    leads = [lead for lead in store.leads.values() if lead.tenant_id == tid]
    messages = [m for m in store.messages.values() if m.tenant_id == tid]
    runs = [r for r in store.runs.values() if r.tenant_id == tid]
    outcomes = [o for o in store.outcomes.values() if o.tenant_id == tid]

    sourced = len(leads)
    scored = sum(1 for lead in leads if lead.score is not None)
    qualified = sum(
        1 for lead in leads if lead.status not in {LeadStatus.NEW.value, LeadStatus.DISQUALIFIED.value}
    )
    enriched = sum(
        1
        for lead in leads
        if lead.status
        not in {
            LeadStatus.NEW.value,
            LeadStatus.DISQUALIFIED.value,
            LeadStatus.QUALIFIED.value,
            LeadStatus.NO_CONTACT.value,
        }
    )
    contacted_leads = [lead for lead in leads if lead.first_contacted_at is not None]
    contacted = len(contacted_leads)
    replied_lead_ids = {m.lead_id for m in messages if m.direction == MessageDirection.INBOUND.value}
    replied = sum(1 for lead in contacted_leads if lead.id in replied_lead_ids)
    positive = sum(1 for lead in contacted_leads if lead.status in POSITIVE_STATUSES)

    won_outcomes = [o for o in outcomes if o.outcome == "won"]
    lost_outcomes = [o for o in outcomes if o.outcome == "lost"]
    win_rate = round(len(won_outcomes) / max(len(won_outcomes) + len(lost_outcomes), 1), 3)
    pipeline_value_egp = sum(o.value_egp or 0.0 for o in won_outcomes)

    total_cost_usd = round(sum(r.total_cost_usd for r in runs), 6)
    cost_per_qualified = round(total_cost_usd / max(qualified, 1), 6)
    cost_per_positive = round(total_cost_usd / max(positive, 1), 6)

    return {
        "range": {"from": from_date, "to": to_date},
        "current": {
            "sourced": sourced,
            "scored": scored,
            "qualified": qualified,
            "qualified_rate": round(qualified / max(scored, 1), 3),
            "contactable_rate": round(enriched / max(qualified, 1), 3),
            "contacted": contacted,
            "reply_rate": round(replied / max(contacted, 1), 3),
            "positive_reply_rate": round(positive / max(contacted, 1), 3),
            "lead_response_time_minutes": 42,
            "our_response_time_minutes": {"agent": 1, "human": 18},
            "won": len(won_outcomes),
            "lost": len(lost_outcomes),
            "win_rate": win_rate,
            "pipeline_value_egp": pipeline_value_egp,
            "llm_cost_usd": total_cost_usd,
            "cost_per_qualified_lead_usd": cost_per_qualified,
            "cost_per_positive_reply_usd": cost_per_positive,
        },
        "previous": {
            "sourced": max(sourced - 12, 0),
            "qualified": max(qualified - 8, 0),
            "contacted": max(contacted - 5, 0),
            "reply_rate": 0.32,
            "win_rate": 0.5,
            "llm_cost_usd": round(total_cost_usd * 0.7, 6),
        },
    }


@router.get("/reports/funnel")
async def reports_funnel(current_user: CurrentUser = Depends(get_mock_current_user)) -> dict[str, Any]:
    store = get_store()
    tid = current_user.tenant_id
    leads = [lead for lead in store.leads.values() if lead.tenant_id == tid]
    messages = [m for m in store.messages.values() if m.tenant_id == tid]
    replied_ids = {m.lead_id for m in messages if m.direction == MessageDirection.INBOUND.value}

    sourced = len(leads)
    qualified = sum(
        1 for lead in leads if lead.status not in {LeadStatus.NEW.value, LeadStatus.DISQUALIFIED.value}
    )
    contacted = sum(1 for lead in leads if lead.first_contacted_at is not None)
    replied = sum(1 for lead in leads if lead.id in replied_ids)
    positive = sum(1 for lead in leads if lead.status in POSITIVE_STATUSES)
    won = sum(1 for lead in leads if lead.status == LeadStatus.WON.value)

    return {
        "stages": [
            {"stage": "sourced", "count": sourced},
            {"stage": "qualified", "count": qualified},
            {"stage": "contacted", "count": contacted},
            {"stage": "replied", "count": replied},
            {"stage": "positive", "count": positive},
            {"stage": "won", "count": won},
        ]
    }


@router.get("/reports/segments")
async def reports_segments(
    by: Literal["governorate", "category", "score_band"] = "governorate",
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> dict[str, Any]:
    store = get_store()
    tid = current_user.tenant_id
    leads = [lead for lead in store.leads.values() if lead.tenant_id == tid]
    messages = [m for m in store.messages.values() if m.tenant_id == tid]
    replied_ids = {m.lead_id for m in messages if m.direction == MessageDirection.INBOUND.value}

    groups: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "contacted": 0, "replied": 0, "won": 0}
    )
    for lead in leads:
        if by == "governorate":
            key = lead.governorate or "Unknown"
        elif by == "category":
            key = lead.category or "Unknown"
        else:
            sc = lead.score
            if sc is None:
                key = "Unscored"
            elif sc <= 3:
                key = "0-3"
            elif sc <= 6:
                key = "4-6"
            elif sc <= 8:
                key = "7-8"
            else:
                key = "9-10"
        groups[key]["total"] += 1
        if lead.first_contacted_at is not None:
            groups[key]["contacted"] += 1
        if lead.id in replied_ids:
            groups[key]["replied"] += 1
        if lead.status == LeadStatus.WON.value:
            groups[key]["won"] += 1

    items = []
    for k, v in groups.items():
        items.append(
            {
                "segment": k,
                **v,
                "reply_rate": round(v["replied"] / max(v["contacted"], 1), 3),
            }
        )
    return {"by": by, "items": items}


@router.get("/reports/costs")
async def reports_costs(current_user: CurrentUser = Depends(get_mock_current_user)) -> dict[str, Any]:
    store = get_store()
    tid = current_user.tenant_id
    runs = [r for r in store.runs.values() if r.tenant_id == tid]
    steps = [s for s in store.steps.values() if s.tenant_id == tid]

    by_kind: dict[str, float] = defaultdict(float)
    for r in runs:
        by_kind[r.kind] = round(by_kind[r.kind] + r.total_cost_usd, 6)

    by_model: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cost_usd": 0.0}
    )
    total_in = 0
    total_cache = 0
    for s in steps:
        if s.model:
            by_model[s.model]["input_tokens"] += s.input_tokens
            by_model[s.model]["output_tokens"] += s.output_tokens
            by_model[s.model]["cache_read_tokens"] += s.cache_read_tokens
            by_model[s.model]["cost_usd"] = round(by_model[s.model]["cost_usd"] + s.cost_usd, 6)
            total_in += s.input_tokens
            total_cache += s.cache_read_tokens

    return {
        "total_cost_usd": round(sum(r.total_cost_usd for r in runs), 6),
        "cache_hit_ratio": round(total_cache / max(total_in, 1), 3),
        "by_kind": [{"kind": k, "cost_usd": v} for k, v in by_kind.items()],
        "by_model": [{"model": m, **vals} for m, vals in by_model.items()],
    }


@router.get("/reports/timeseries")
async def reports_timeseries(
    metric: Literal["sourced", "contacted", "replies"] = "sourced",
    current_user: CurrentUser = Depends(get_mock_current_user),
) -> dict[str, Any]:
    store = get_store()
    tid = current_user.tenant_id
    leads = [lead for lead in store.leads.values() if lead.tenant_id == tid]
    messages = [m for m in store.messages.values() if m.tenant_id == tid]

    counts_by_day: dict[str, int] = defaultdict(int)
    if metric == "sourced":
        for lead in leads:
            counts_by_day[lead.created_at.date().isoformat()] += 1
    elif metric == "contacted":
        for lead in leads:
            if lead.first_contacted_at:
                counts_by_day[lead.first_contacted_at.date().isoformat()] += 1
    else:
        for m in messages:
            if m.direction == MessageDirection.INBOUND.value:
                counts_by_day[m.created_at.date().isoformat()] += 1

    series = [{"date": d, "count": c} for d, c in sorted(counts_by_day.items())]
    return {"metric": metric, "series": series}


@router.get("/insights")
async def list_insights(current_user: CurrentUser = Depends(get_mock_current_user)) -> dict[str, Any]:
    store = get_store()
    rows = [i for i in store.insights.values() if i.tenant_id == current_user.tenant_id]
    rows.sort(key=lambda i: i.version, reverse=True)
    active = next((i for i in rows if i.is_active), None)
    return {
        "active": (
            {
                "id": str(active.id),
                "version": active.version,
                "insights": active.insights,
                "stats": active.stats,
                "is_active": active.is_active,
                "created_at": active.created_at,
            }
            if active
            else None
        ),
        "history": [
            {
                "id": str(i.id),
                "version": i.version,
                "insights": i.insights,
                "stats": i.stats,
                "is_active": i.is_active,
                "created_at": i.created_at,
            }
            for i in rows
        ],
    }


@router.post("/insights/run", status_code=202)
async def run_feedback_insights(current_user: CurrentUser = Depends(get_mock_current_user)) -> dict[str, Any]:
    store = get_store()
    tid = current_user.tenant_id
    outcomes = [o for o in store.outcomes.values() if o.tenant_id == tid]
    if len(outcomes) < 3:
        raise AppError(
            "not_enough_outcomes", "At least 3 won/lost outcomes are required to generate insights.", 400
        )

    existing = [i for i in store.insights.values() if i.tenant_id == tid]
    for i in existing:
        i.is_active = False
    next_ver = max((i.version for i in existing), default=0) + 1
    now = datetime.now(UTC)

    new_insight = MockLearnedInsight(
        id=uuid.uuid4(),
        tenant_id=tid,
        version=next_ver,
        insights=[
            "محلات الأطفال في القاهرة الجديدة والمهندسين تحقق أعلى نسبة إغلاق صفقات (Win Rate 67%).",
            "تقديم عرض الشحن المجاني في الرسالة الأولى رفع التفاعل بنسبة 35%.",
            "يفضل استبعاد المحلات العامة ذات التقييم أقل من 4.0 لتقليل تكلفة المتابعة.",
        ],
        stats={"total_outcomes": len(outcomes), "generated_at": now.isoformat()},
        is_active=True,
        created_at=now,
    )
    store.insights[new_insight.id] = new_insight

    run = MockAgentRun(
        id=uuid.uuid4(),
        tenant_id=tid,
        kind=AgentRunKind.FEEDBACK.value,
        status=AgentRunStatus.SUCCEEDED.value,
        trigger="manual",
        input={"outcomes_count": len(outcomes)},
        output_summary={"version": next_ver, "insights_count": len(new_insight.insights)},
        created_at=now,
        started_at=now,
        finished_at=now + timedelta(seconds=2),
        total_input_tokens=1800,
        total_output_tokens=450,
        total_cost_usd=0.0045,
    )
    store.runs[run.id] = run
    return {"run_id": str(run.id), "insight_id": str(new_insight.id), "version": next_ver}


@router.post("/insights/{insight_id}/deactivate")
async def deactivate_insight(
    insight_id: uuid.UUID, current_user: CurrentUser = Depends(get_mock_current_user)
) -> dict[str, Any]:
    store = get_store()
    ins = store.insights.get(insight_id)
    if ins is None or ins.tenant_id != current_user.tenant_id:
        raise NotFoundError("insight")
    ins.is_active = False
    return {"id": str(ins.id), "is_active": ins.is_active}
