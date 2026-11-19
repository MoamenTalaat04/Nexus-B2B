"""Mock Business Settings & Geo routes: /settings, /settings/geo."""

from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.core.geo_eg_coords import GOVERNORATES
from app.core.security import CurrentUser
from app.mock_api.helpers import get_mock_current_user, get_tenant_settings, is_eg_mobile, normalize_eg_phone
from app.mock_api.state import get_store
from app.models.enums import AutonomyMode, FirstTouchMode

router = APIRouter(prefix="/settings", tags=["settings"])


class ProductItem(BaseModel):
    name: str
    description: str = ""
    price_range: str | None = None
    min_order: str | None = None


class RegionItem(BaseModel):
    governorate: str
    cities: list[str] = []


class SequenceStepItem(BaseModel):
    day_offset: int = Field(ge=0)
    purpose: str
    template: str


class SettingsOut(BaseModel):
    company_name: str
    website: str | None
    description: str
    ideal_customer_text: str
    products: list[ProductItem]
    target_regions: list[RegionItem]
    language: str
    tone: str
    allowed_offers: str
    max_discount_percent: int
    autonomy_mode: str
    first_touch_mode: str
    agent_enabled: bool
    daily_new_leads_target: int
    daily_send_cap: int
    quiet_hours_start: time
    quiet_hours_end: time
    working_days: list[int]
    score_threshold: int
    sequence_steps: list[SequenceStepItem]
    demo_mode: bool
    demo_whitelist: list[str]
    telegram_connected: bool
    onboarding_completed: bool


class SettingsUpdateIn(BaseModel):
    company_name: str | None = None
    website: str | None = None
    description: str | None = None
    ideal_customer_text: str | None = None
    products: list[ProductItem] | None = Field(default=None, max_length=30)
    target_regions: list[RegionItem] | None = None
    language: Literal["ar-EG", "en"] | None = None
    tone: Literal["friendly", "formal"] | None = None
    allowed_offers: str | None = None
    max_discount_percent: int | None = Field(default=None, ge=0, le=50)
    autonomy_mode: AutonomyMode | None = None
    first_touch_mode: FirstTouchMode | None = None
    agent_enabled: bool | None = None
    daily_new_leads_target: int | None = Field(default=None, ge=1, le=200)
    daily_send_cap: int | None = Field(default=None, ge=1, le=200)
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    working_days: list[int] | None = None
    score_threshold: int | None = Field(default=None, ge=1, le=10)
    sequence_steps: list[SequenceStepItem] | None = Field(default=None, min_length=1, max_length=4)
    demo_mode: bool | None = None
    demo_whitelist: list[str] | None = Field(default=None, max_length=5)
    onboarding_completed: bool | None = None


def _to_out(s: Any) -> SettingsOut:
    return SettingsOut(
        company_name=s.company_name,
        website=s.website,
        description=s.description,
        ideal_customer_text=s.ideal_customer_text,
        products=[ProductItem(**p) for p in s.products],
        target_regions=[RegionItem(**r) for r in s.target_regions],
        language=s.language,
        tone=s.tone,
        allowed_offers=s.allowed_offers,
        max_discount_percent=s.max_discount_percent,
        autonomy_mode=s.autonomy_mode,
        first_touch_mode=s.first_touch_mode,
        agent_enabled=s.agent_enabled,
        daily_new_leads_target=s.daily_new_leads_target,
        daily_send_cap=s.daily_send_cap,
        quiet_hours_start=s.quiet_hours_start,
        quiet_hours_end=s.quiet_hours_end,
        working_days=list(s.working_days),
        score_threshold=s.score_threshold,
        sequence_steps=[SequenceStepItem(**st) for st in s.sequence_steps],
        demo_mode=s.demo_mode,
        demo_whitelist=list(s.demo_whitelist),
        telegram_connected=bool(s.telegram_chat_id),
        onboarding_completed=s.onboarding_completed,
    )


@router.get("", response_model=SettingsOut)
async def get_settings(current_user: CurrentUser = Depends(get_mock_current_user)) -> SettingsOut:
    store = get_store()
    s = get_tenant_settings(store, current_user.tenant_id)
    return _to_out(s)


@router.put("", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdateIn, current_user: CurrentUser = Depends(get_mock_current_user)
) -> SettingsOut:
    store = get_store()
    s = get_tenant_settings(store, current_user.tenant_id)
    data = body.model_dump(exclude_unset=True)

    new_start = data.get("quiet_hours_start", s.quiet_hours_start)
    new_end = data.get("quiet_hours_end", s.quiet_hours_end)
    if new_start >= new_end:
        raise AppError(
            "invalid_quiet_hours", "quiet_hours_start must be before quiet_hours_end", status_code=422
        )

    if "demo_whitelist" in data and data["demo_whitelist"] is not None:
        normalized: list[str] = []
        for raw in data["demo_whitelist"]:
            e164 = normalize_eg_phone(raw)
            if not e164 or not is_eg_mobile(e164):
                raise AppError("invalid_phone", f"Invalid Egyptian mobile number: {raw}", status_code=422)
            normalized.append(e164)
        data["demo_whitelist"] = normalized

    if "autonomy_mode" in data and data["autonomy_mode"] is not None:
        data["autonomy_mode"] = data["autonomy_mode"].value
    if "first_touch_mode" in data and data["first_touch_mode"] is not None:
        data["first_touch_mode"] = data["first_touch_mode"].value

    for key, val in data.items():
        setattr(s, key, val)
    s.updated_at = datetime.now(UTC)
    return _to_out(s)


@router.get("/geo")
async def get_geo() -> dict[str, Any]:
    """Return Egyptian governorates and cities from app.core.geo_eg_coords."""
    return {
        "governorates": [
            {
                "name": g.name,
                "name_ar": g.name_ar,
                "cities": list(g.cities.keys()),
            }
            for g in GOVERNORATES.values()
        ]
    }
