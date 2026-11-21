"""CRM routes (P4-1, CONTRACTS section 11). The list and /leads/stats belong to P2-4 (app/api/leads.py, D).

GET   /api/v1/leads/export.xlsx          Excel export (same filters as the list)
GET   /api/v1/leads/{id}                 lead + contacts + messages + history + notes + outcome
PATCH /api/v1/leads/{id}                 {status?, agent_paused?}
POST  /api/v1/leads/{id}/notes           {body}
POST  /api/v1/leads/{id}/outcome         {outcome: won|lost, value_egp?, reason?}
POST  /api/v1/leads/{id}/contacts        {type, value}
POST  /api/v1/leads/{id}/messages        {body}  manual text; 409 window_closed outside the 24h window
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db import get_session
from app.models.enums import LeadStatus
from app.services import crm

router = APIRouter(prefix="/leads", tags=["crm"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/export.xlsx", response_class=Response)
async def export_leads(
    status: LeadStatus | None = None,
    min_score: int | None = None,
    q: str | None = None,
    governorate: str | None = None,
    sourcing_run_id: uuid.UUID | None = None,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    filters = crm.LeadFilters(
        status=status, min_score=min_score, q=q, governorate=governorate, sourcing_run_id=sourcing_run_id
    )
    content = crm.build_workbook(await crm.export_rows(session, user.tenant_id, filters))
    name = f"leads-{datetime.now(UTC):%Y%m%d}.xlsx"
    return Response(
        content, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"'}
    )


@router.get("/{lead_id}", response_model=crm.LeadDetailOut)
async def get_lead_detail(
    lead_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> crm.LeadDetailOut:
    return await crm.lead_detail(session, user.tenant_id, lead_id)


@router.patch("/{lead_id}", response_model=crm.LeadDetailOut)
async def patch_lead(
    lead_id: uuid.UUID,
    data: crm.LeadPatchIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> crm.LeadDetailOut:
    await crm.patch_lead(session, user.tenant_id, lead_id, user.user_id, data)
    return await crm.lead_detail(session, user.tenant_id, lead_id)


@router.post("/{lead_id}/notes", response_model=crm.NoteOut, status_code=201)
async def add_note(
    lead_id: uuid.UUID,
    data: crm.NoteIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> crm.NoteOut:
    return await crm.add_note(session, user.tenant_id, lead_id, user.user_id, data)


@router.post("/{lead_id}/outcome", response_model=crm.OutcomeOut, status_code=201)
async def record_outcome(
    lead_id: uuid.UUID,
    data: crm.OutcomeIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> crm.OutcomeOut:
    return await crm.record_outcome(session, user.tenant_id, lead_id, user.user_id, data)


@router.post("/{lead_id}/contacts", response_model=crm.ContactOut, status_code=201)
async def add_contact(
    lead_id: uuid.UUID,
    data: crm.ContactIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> crm.ContactOut:
    return await crm.add_contact(session, user.tenant_id, lead_id, user.user_id, data)


@router.post("/{lead_id}/messages", response_model=crm.MessageOut, status_code=201)
async def send_message(
    lead_id: uuid.UUID,
    data: crm.ManualMessageIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> crm.MessageOut:
    return await crm.send_manual_message(session, user.tenant_id, lead_id, data)
