"""Reports API (P4-3, CONTRACTS section 11). Metric definitions live in app/services/reports.py.

GET /api/v1/reports/summary?from=&to=          → KPIs with the previous equal-length period and deltas
GET /api/v1/reports/funnel?from=&to=           → sourced → qualified → contacted → replied → positive → won
GET /api/v1/reports/segments?by=&from=&to=     → by governorate | category | score_band
GET /api/v1/reports/costs?from=&to=            → AI cost by kind (daily), per model, cache hit ratio
GET /api/v1/reports/timeseries?metric=&from=&to= → daily sourced | contacted | replies | won

`from`/`to` are calendar days (YYYY-MM-DD) in Africa/Cairo, both inclusive; the default is the last 30 days.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db import get_session
from app.services import reports

router = APIRouter(prefix="/reports", tags=["reports"])

FromQuery = Query(None, alias="from", description="First day (YYYY-MM-DD, Cairo), inclusive")
ToQuery = Query(None, alias="to", description="Last day (YYYY-MM-DD, Cairo), inclusive")


@router.get("/summary", response_model=reports.SummaryOut)
async def get_summary(
    from_date: date | None = FromQuery,
    to_date: date | None = ToQuery,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> reports.SummaryOut:
    return await reports.summary(session, user.tenant_id, reports.resolve_range(from_date, to_date))


@router.get("/funnel", response_model=reports.FunnelOut)
async def get_funnel(
    from_date: date | None = FromQuery,
    to_date: date | None = ToQuery,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> reports.FunnelOut:
    return await reports.funnel(session, user.tenant_id, reports.resolve_range(from_date, to_date))


@router.get("/segments", response_model=reports.SegmentsOut)
async def get_segments(
    by: reports.SegmentBy = "governorate",
    from_date: date | None = FromQuery,
    to_date: date | None = ToQuery,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> reports.SegmentsOut:
    return await reports.segments(session, user.tenant_id, reports.resolve_range(from_date, to_date), by)


@router.get("/costs", response_model=reports.CostsOut)
async def get_costs(
    from_date: date | None = FromQuery,
    to_date: date | None = ToQuery,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> reports.CostsOut:
    return await reports.costs(session, user.tenant_id, reports.resolve_range(from_date, to_date))


@router.get("/timeseries", response_model=reports.TimeseriesOut)
async def get_timeseries(
    metric: reports.Metric = "sourced",
    from_date: date | None = FromQuery,
    to_date: date | None = ToQuery,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> reports.TimeseriesOut:
    return await reports.timeseries(
        session, user.tenant_id, reports.resolve_range(from_date, to_date), metric
    )
