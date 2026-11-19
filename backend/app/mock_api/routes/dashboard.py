"""Mock Dashboard route: GET /dashboard (computed consistently from mock state)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends

from app.core.security import CurrentUser
from app.mock_api.helpers import get_mock_current_user, get_tenant_settings
from app.mock_api.state import get_store
from app.models.enums import LeadStatus, MessageDirection, MessageStatus

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

HOT_STATUSES = {
    LeadStatus.INTERESTED.value,
    LeadStatus.WANTS_OFFER.value,
    LeadStatus.WANTS_MANAGEMENT.value,
}
QUALIFIED_OR_LATER = {s.value for s in LeadStatus if s not in {LeadStatus.NEW, LeadStatus.DISQUALIFIED}}


@router.get("")
async def get_dashboard(current_user: CurrentUser = Depends(get_mock_current_user)) -> dict[str, Any]:
    store = get_store()
    tid = current_user.tenant_id
    s = get_tenant_settings(store, tid)

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    leads = [lead for lead in store.leads.values() if lead.tenant_id == tid]
    messages = [m for m in store.messages.values() if m.tenant_id == tid]
    runs = sorted(
        (r for r in store.runs.values() if r.tenant_id == tid), key=lambda r: r.created_at, reverse=True
    )
    notifications = sorted(
        (n for n in store.notifications.values() if n.tenant_id == tid),
        key=lambda n: n.created_at,
        reverse=True,
    )

    # Note: seed timestamps use BASE_TIME (2026-11-19), so check >= today_start OR latest date if needed
    today_new = sum(1 for lead in leads if lead.created_at >= today_start)
    week_new = sum(1 for lead in leads if lead.created_at >= week_start)
    qualified_count = sum(1 for lead in leads if lead.status in QUALIFIED_OR_LATER)
    messages_sent = sum(
        1
        for m in messages
        if m.direction == MessageDirection.OUTBOUND.value
        and m.status in {MessageStatus.SENT.value, MessageStatus.DELIVERED.value, MessageStatus.READ.value}
    )
    replies_count = sum(1 for m in messages if m.direction == MessageDirection.INBOUND.value)
    hot_leads = [lead for lead in leads if lead.status in HOT_STATUSES]
    hot_leads.sort(key=lambda lead: lead.last_inbound_at or lead.created_at, reverse=True)
    won_count = sum(1 for lead in leads if lead.status == LeadStatus.WON.value)

    pending_approvals = sum(1 for m in messages if m.status == MessageStatus.PENDING_APPROVAL.value)
    assisted_waiting = sum(1 for m in messages if m.status == MessageStatus.AWAITING_MANUAL_SEND.value)
    wants_management = sum(1 for lead in leads if lead.status == LeadStatus.WANTS_MANAGEMENT.value)

    week_cost = round(sum(r.total_cost_usd for r in runs if r.created_at >= week_start), 6)
    last_run = runs[0] if runs else None

    next_run_dt = today_start + timedelta(days=1, hours=7)  # 09:00 Africa/Cairo (UTC+2)

    return {
        "kpis": {
            "today_new_leads": today_new,
            "week_new_leads": week_new,
            "total_leads": len(leads),
            "qualified_leads": qualified_count,
            "messages_sent": messages_sent,
            "replies": replies_count,
            "hot_leads": len(hot_leads),
            "won_leads": won_count,
            "week_llm_cost_usd": week_cost,
        },
        "agent": {
            "enabled": s.agent_enabled,
            "demo_mode": s.demo_mode,
            "autonomy_mode": s.autonomy_mode,
            "first_touch_mode": s.first_touch_mode,
            "last_run": (
                {
                    "id": str(last_run.id),
                    "kind": last_run.kind,
                    "status": last_run.status,
                    "created_at": last_run.created_at,
                    "output_summary": last_run.output_summary,
                }
                if last_run
                else None
            ),
            "next_scheduled_run": next_run_dt if s.agent_enabled else None,
        },
        "attention": {
            "pending_approvals": pending_approvals,
            "assisted_waiting": assisted_waiting,
            "wants_management": wants_management,
        },
        "latest_hot_leads": [
            {
                "id": str(lead.id),
                "name": lead.name,
                "governorate": lead.governorate,
                "city": lead.city,
                "status": lead.status,
                "score": lead.score,
                "last_inbound_at": lead.last_inbound_at,
            }
            for lead in hot_leads[:5]
        ],
        "latest_notifications": [
            {
                "id": str(n.id),
                "lead_id": str(n.lead_id) if n.lead_id else None,
                "kind": n.kind,
                "title": n.title,
                "body": n.body,
                "read_at": n.read_at,
                "created_at": n.created_at,
            }
            for n in notifications[:5]
        ],
        "unread_notifications_count": sum(1 for n in notifications if n.read_at is None),
    }
