"""Leads list and stats API (P2-4, CONTRACTS section 11)."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import ColumnElement, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db import get_session
from app.models.enums import LeadStatus
from app.models.leads import Lead
from app.schemas.leads import LeadListOut, LeadStatsOut, LeadSummaryOut

router = APIRouter(prefix="/leads", tags=["leads"])


def _build_filters(
    *,
    tenant_id: uuid.UUID,
    status: LeadStatus | None,
    min_score: int | None,
    q: str | None,
    governorate: str | None,
    sourcing_run_id: uuid.UUID | None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [Lead.tenant_id == tenant_id]
    if status is not None:
        filters.append(Lead.status == status.value)
    if min_score is not None:
        filters.append(Lead.score.is_not(None))
        filters.append(Lead.score >= min_score)
    if governorate:
        filters.append(Lead.governorate.ilike(f"%{governorate.strip()}%"))
    if sourcing_run_id is not None:
        filters.append(Lead.sourcing_run_id == sourcing_run_id)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Lead.name.ilike(pattern),
                Lead.category.ilike(pattern),
                Lead.city.ilike(pattern),
                Lead.governorate.ilike(pattern),
                Lead.ref_code.ilike(pattern),
            )
        )
    return filters


@router.get("", response_model=LeadListOut)
async def list_leads(
    status: LeadStatus | None = None,
    min_score: int | None = Query(default=None, ge=0, le=10),
    q: str | None = None,
    governorate: str | None = None,
    sourcing_run_id: uuid.UUID | None = None,
    sort: Literal["created_at", "score", "name"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LeadListOut:
    filters = _build_filters(
        tenant_id=user.tenant_id,
        status=status,
        min_score=min_score,
        q=q,
        governorate=governorate,
        sourcing_run_id=sourcing_run_id,
    )
    total = int((await session.execute(select(func.count()).select_from(Lead).where(*filters))).scalar_one())

    sort_col = {
        "created_at": Lead.created_at,
        "score": Lead.score,
        "name": Lead.name,
    }[sort]
    order_fn = asc if order == "asc" else desc

    rows = (
        (
            await session.execute(
                select(Lead)
                .where(*filters)
                .order_by(order_fn(sort_col).nulls_last(), Lead.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return LeadListOut(
        items=[
            LeadSummaryOut(
                id=row.id,
                ref_code=row.ref_code,
                source=row.source,
                name=row.name,
                category=row.category,
                address=row.address,
                city=row.city,
                governorate=row.governorate,
                website=row.website,
                rating=row.rating,
                reviews_count=row.reviews_count,
                status=row.status,
                score=row.score,
                score_reasons=list(row.score_reasons or []),
                disqualify_reason=row.disqualify_reason,
                sourcing_run_id=row.sourcing_run_id,
                agent_paused=row.agent_paused,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=LeadStatsOut)
async def leads_stats(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LeadStatsOut:
    rows = (
        await session.execute(
            select(Lead.status, func.count()).where(Lead.tenant_id == user.tenant_id).group_by(Lead.status)
        )
    ).all()
    by_status = {str(status_val): int(count) for status_val, count in rows}
    total = sum(by_status.values())
    avg_raw = await session.scalar(
        select(func.avg(Lead.score)).where(Lead.tenant_id == user.tenant_id, Lead.score.is_not(None))
    )
    return LeadStatsOut(
        total=total,
        by_status=by_status,
        avg_score=round(float(avg_raw), 2) if avg_raw is not None else None,
        qualified_count=by_status.get(LeadStatus.QUALIFIED.value, 0),
        enriched_count=by_status.get(LeadStatus.ENRICHED.value, 0),
        contacted_count=by_status.get(LeadStatus.CONTACTED.value, 0),
        won_count=by_status.get(LeadStatus.WON.value, 0),
    )
