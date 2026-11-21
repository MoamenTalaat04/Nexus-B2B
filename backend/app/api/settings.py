"""Business settings API (P1-2, CONTRACTS section 11). The onboarding wizard and Settings pages (D) use it.

GET /api/v1/settings        → SettingsOut (the default row is created on first read)
PUT /api/v1/settings        SettingsUpdate (partial: only the fields sent change) → SettingsOut
GET /api/v1/settings/geo    → {"governorates": [{name, name_ar, cities: [{name, name_ar}]}]}

Rules checked after merging the change with the stored values:
- quiet_hours_start < quiet_hours_end (the sending window, Africa/Cairo);
- onboarding_completed=true needs company_name, at least one product and one target region
  (POST /icp/generate answers 400 onboarding_incomplete until it is true);
- only an owner can change settings (members get 403).
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import geo_eg
from app.core.errors import AppError
from app.core.security import CurrentUser, get_current_user
from app.core.tenancy import get_settings_for
from app.db import get_session
from app.models.tenants import BusinessSettings
from app.schemas.settings import SEND_CAP_WARNING_ABOVE, GeoOut, SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

OUT_FIELDS = [name for name in SettingsOut.model_fields if name not in {"telegram_connected", "warnings"}]


def warnings_for(row: BusinessSettings) -> list[str]:
    out: list[str] = []
    if row.daily_send_cap > SEND_CAP_WARNING_ABOVE:
        out.append("daily_send_cap_above_50")  # higher volumes risk a WhatsApp quality downgrade
    if row.demo_mode and not row.demo_whitelist:
        out.append("demo_whitelist_empty")  # demo mode blocks every send until a test phone is added
    if not row.demo_mode:
        out.append("demo_mode_off")  # messages go to the leads' real numbers
    return out


def to_out(row: BusinessSettings) -> SettingsOut:
    values: dict[str, Any] = {name: getattr(row, name) for name in OUT_FIELDS}
    return SettingsOut(**values, telegram_connected=bool(row.telegram_chat_id), warnings=warnings_for(row))


def _check_merged(row: BusinessSettings, changes: dict[str, Any]) -> None:
    start = changes.get("quiet_hours_start", row.quiet_hours_start)
    end = changes.get("quiet_hours_end", row.quiet_hours_end)
    if start >= end:
        raise AppError(
            "invalid_quiet_hours",
            "The sending window must start before it ends (e.g. 10:00 → 20:00).",
            status_code=422,
        )
    if changes.get("onboarding_completed") is True:
        missing = [
            label
            for label, value in (
                ("company_name", changes.get("company_name", row.company_name)),
                ("products", changes.get("products", row.products)),
                ("target_regions", changes.get("target_regions", row.target_regions)),
            )
            if not value
        ]
        if missing:
            raise AppError(
                "onboarding_incomplete",
                "Before finishing onboarding, fill in: " + ", ".join(missing) + ".",
                status_code=422,
            )


async def update_settings(
    session: AsyncSession, tenant_id: uuid.UUID, body: SettingsUpdate
) -> BusinessSettings:
    """Apply a partial update to the tenant's settings (flushed; the caller commits)."""
    row = await get_settings_for(session, tenant_id)
    changes = body.changes()
    _check_merged(row, changes)
    for name, value in changes.items():
        setattr(row, name, value)
    await session.flush()
    return row


@router.get("", response_model=SettingsOut)
async def get_settings(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SettingsOut:
    row = await get_settings_for(session, user.tenant_id)
    await session.commit()  # keeps the default row if it was just created
    return to_out(row)


@router.put("", response_model=SettingsOut)
async def put_settings(
    body: SettingsUpdate,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SettingsOut:
    if user.role != "owner":
        raise AppError("forbidden", "Only the account owner can change the settings.", status_code=403)
    row = await update_settings(session, user.tenant_id, body)
    await session.commit()
    await session.refresh(row)
    return to_out(row)


@router.get("/geo", response_model=GeoOut)
async def get_geo(_: CurrentUser = Depends(get_current_user)) -> GeoOut:
    return GeoOut.model_validate({"governorates": geo_eg.as_json()})
