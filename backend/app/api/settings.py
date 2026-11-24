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

import asyncio
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import geo_eg
from app.core.errors import AppError
from app.core.security import CurrentUser, get_current_user
from app.core.tenancy import get_settings_for
from app.db import get_session
from app.models.tenants import BusinessSettings
from app.schemas.settings import (
    SEND_CAP_WARNING_ABOVE,
    AiQuotaOut,
    CompanyAiAssistIn,
    CompanyAiAssistOut,
    GeoCircleResolveIn,
    GeoCircleResolveOut,
    GeoOut,
    OfferingsAiExtractOut,
    RegionIn,
    SettingsOut,
    SettingsUpdate,
)
from app.services.company_assist import assist_company_field, extract_offerings_from_source, get_ai_quota_summary

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


@router.post("/geo/resolve-circle", response_model=GeoCircleResolveOut)
async def resolve_geo_circle(
    body: GeoCircleResolveIn,
    _: CurrentUser = Depends(get_current_user),
) -> GeoCircleResolveOut:
    """Resolve all states/governorates and their cities/neighborhoods inside a map circle."""
    headers = {"User-Agent": "Nexus-B2B-GeoResolver/1.0"}
    radius_m = int(body.radius_km * 1000)

    async def _nominatim_reverse(client: httpx.AsyncClient) -> dict[str, Any]:
        try:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "format": "jsonv2",
                    "lat": body.lat,
                    "lon": body.lng,
                    "zoom": 10,
                    "addressdetails": 1,
                    "accept-language": "en",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, dict) else {}
        except httpx.HTTPError:
            pass
        return {}

    async def _overpass_data(client: httpx.AsyncClient) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        query = (
            f"[out:json][timeout:10];"
            f"("
            f'node["place"~"^(city|town|suburb|neighbourhood|quarter)$"](around:{radius_m},{body.lat},{body.lng});'
            f'relation["boundary"="administrative"]["admin_level"="4"](around:{radius_m},{body.lat},{body.lng});'
            f");"
            f"out tags bb 80;"
        )
        try:
            resp = await client.post("https://overpass-api.de/api/interpreter", data={"data": query})
            if resp.status_code != 200:
                return [], []
            elements = resp.json().get("elements", [])
            nodes = [el for el in elements if el.get("type") == "node"]
            rels = [el for el in elements if el.get("type") == "relation" and el.get("bounds")]
            return nodes, rels
        except Exception:
            return [], []

    async with httpx.AsyncClient(timeout=httpx.Timeout(12.0), headers=headers) as client:
        rev, (nodes, state_rels) = await asyncio.gather(
            _nominatim_reverse(client),
            _overpass_data(client),
        )

    addr = rev.get("address") if isinstance(rev.get("address"), dict) else {}
    center_country = str(addr.get("country") or "Unknown").strip()
    center_state = str(
        addr.get("state")
        or addr.get("governorate")
        or addr.get("region")
        or addr.get("province")
        or addr.get("county")
        or addr.get("city")
        or center_country
    ).strip()

    # Precompute state bounding boxes sorted by smallest area first for accurate point-in-box matching
    parsed_states: list[tuple[float, str, dict[str, float]]] = []
    for rel in state_rels:
        tags = rel.get("tags") or {}
        state_name = str(tags.get("name:en") or tags.get("name") or "").strip()
        bounds = rel.get("bounds") or {}
        if not state_name or not all(k in bounds for k in ("minlat", "maxlat", "minlon", "maxlon")):
            continue
        area = abs(float(bounds["maxlat"]) - float(bounds["minlat"])) * abs(
            float(bounds["maxlon"]) - float(bounds["minlon"])
        )
        parsed_states.append((area, state_name, bounds))
    parsed_states.sort(key=lambda item: item[0])

    def _state_for_node(tags: dict[str, Any], nlat: float | None, nlon: float | None) -> str:
        explicit = str(tags.get("addr:state") or tags.get("is_in:state") or "").strip()
        if explicit:
            return explicit
        if nlat is not None and nlon is not None:
            for _area, s_name, b in parsed_states:
                if float(b["minlat"]) <= nlat <= float(b["maxlat"]) and float(b["minlon"]) <= nlon <= float(b["maxlon"]):
                    return s_name
        return center_state

    grouped: dict[str, list[str]] = {}
    for node in nodes:
        tags = node.get("tags") or {}
        place_name = str(tags.get("name:en") or tags.get("name") or "").strip()
        if not place_name:
            continue
        nlat = node.get("lat")
        nlon = node.get("lon")
        st = _state_for_node(tags, float(nlat) if nlat is not None else None, float(nlon) if nlon is not None else None)
        bucket = grouped.setdefault(st, [])
        if place_name[:80] not in bucket and len(bucket) < 30:
            bucket.append(place_name[:80])

    if not grouped:
        fallback_places: list[str] = []
        for key in ("city", "town", "suburb", "neighbourhood", "county"):
            val = str(addr.get(key) or "").strip()
            if val and val not in fallback_places:
                fallback_places.append(val[:80])
        grouped[center_state] = fallback_places

    regions = [
        RegionIn(
            country=center_country,
            governorate=st,
            cities=cities,
            lat=round(body.lat, 5),
            lng=round(body.lng, 5),
            radius_km=round(body.radius_km, 1),
        )
        for st, cities in grouped.items()
    ]
    return GeoCircleResolveOut(regions=regions)


@router.get("/ai-quota", response_model=AiQuotaOut)
async def get_ai_quota(user: CurrentUser = Depends(get_current_user)) -> AiQuotaOut:
    data = await get_ai_quota_summary(user.tenant_id)
    return AiQuotaOut(**data)


@router.post("/ai-assist", response_model=CompanyAiAssistOut)
async def ai_assist_company(
    body: CompanyAiAssistIn,
    user: CurrentUser = Depends(get_current_user),
) -> CompanyAiAssistOut:
    if user.role != "owner":
        raise AppError("forbidden", "Only the account owner can use AI onboarding assist.", status_code=403)
    text, source_summary = await assist_company_field(
        tenant_id=user.tenant_id,
        field=body.field,
        mode=body.mode,
        company_name=body.company_name,
        website=body.website,
        current_text=body.current_text,
        other_text=body.other_text,
    )
    return CompanyAiAssistOut(text=text, source_summary=source_summary)


@router.post("/ai-extract-offerings", response_model=OfferingsAiExtractOut)
async def ai_extract_offerings(
    file: UploadFile | None = File(default=None),
    company_name: str = Form(default=""),
    website: str = Form(default=""),
    description: str = Form(default=""),
    user: CurrentUser = Depends(get_current_user),
) -> OfferingsAiExtractOut:
    if user.role != "owner":
        raise AppError("forbidden", "Only the account owner can use AI onboarding assist.", status_code=403)
    file_bytes: bytes | None = None
    filename = ""
    mime_type = ""
    if file is not None:
        file_bytes = await file.read()
        filename = file.filename or "catalog"
        mime_type = file.content_type or ""
    items, source_summary = await extract_offerings_from_source(
        tenant_id=user.tenant_id,
        company_name=company_name,
        website=website or None,
        description=description,
        file_bytes=file_bytes,
        filename=filename,
        mime_type=mime_type,
    )
    return OfferingsAiExtractOut(items=items, source_summary=source_summary)
