"""P1-2: GET/PUT /api/v1/settings and GET /api/v1/settings/geo."""

import uuid
from typing import Any

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.models.tenants import Tenant


def auth(tenant_id: uuid.UUID, role: str = "owner") -> dict[str, str]:
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "tid": str(tenant_id), "role": role}, app_settings.JWT_SECRET, "HS256"
    )
    return {"Cookie": f"access_token={token}"}


@pytest.fixture
async def tenant(session: AsyncSession) -> Tenant:
    row = Tenant(name="Little Stars")
    session.add(row)
    await session.flush()
    return row


PRODUCT = {
    "name": "بيجامات أطفال",
    "description": "قطن 100%",
    "price_range": "120-250 EGP",
    "min_order": "1 dozen",
}


async def put(client: AsyncClient, tenant: Tenant, body: dict[str, Any], role: str = "owner") -> Any:
    return await client.put("/api/v1/settings", json=body, headers=auth(tenant.id, role))


async def test_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/settings")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_get_returns_defaults(client: AsyncClient, tenant: Tenant) -> None:
    resp = await client.get("/api/v1/settings", headers=auth(tenant.id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["quiet_hours_start"] == "10:00" and body["quiet_hours_end"] == "20:00"
    assert body["working_days"] == [0, 1, 2, 3, 5, 6]
    assert body["autonomy_mode"] == "approve_all" and body["first_touch_mode"] == "assisted"
    assert body["demo_mode"] is True and body["demo_whitelist"] == []
    assert body["onboarding_completed"] is False
    assert body["sequence_steps"][0] == {"day_offset": 0, "purpose": "first_touch", "template": "intro"}
    assert "demo_whitelist_empty" in body["warnings"]
    assert body["telegram_connected"] is False


async def test_partial_update_changes_only_sent_fields(client: AsyncClient, tenant: Tenant) -> None:
    resp = await put(client, tenant, {"company_name": "Little Stars Kids Wear", "max_discount_percent": 10})
    assert resp.status_code == 200, resp.text
    resp = await put(client, tenant, {"daily_send_cap": 15})
    body = resp.json()
    assert body["company_name"] == "Little Stars Kids Wear"
    assert body["max_discount_percent"] == 10
    assert body["daily_send_cap"] == 15
    assert body["daily_new_leads_target"] == 30


async def test_full_onboarding_payload(client: AsyncClient, tenant: Tenant) -> None:
    resp = await put(
        client,
        tenant,
        {
            "company_name": "Little Stars Kids Wear",
            "website": "littlestars.example",
            "description": "مصنع ملابس أطفال في العاشر من رمضان",
            "ideal_customer_text": "محلات ملابس الأطفال في القاهرة والجيزة",
            "products": [PRODUCT],
            "target_regions": [
                {"governorate": "cairo", "cities": ["مدينة نصر", "Heliopolis"]},
                {"governorate": "Giza", "cities": []},
            ],
            "language": "ar-EG",
            "tone": "friendly",
            "allowed_offers": "خصم لحد 10% على أول طلب",
            "autonomy_mode": "approve_first_touch",
            "first_touch_mode": "api_template",
            "quiet_hours_start": "09:30",
            "quiet_hours_end": "21:00",
            "working_days": [6, 0, 1, 1],
            "score_threshold": 7,
            "sequence_steps": [
                {"day_offset": 0, "purpose": "first_touch", "template": "intro"},
                {"day_offset": 3, "purpose": "followup", "template": "followup"},
                {"day_offset": 7, "purpose": "followup", "template": "followup"},
            ],
            "demo_whitelist": ["010 0000 0001", "+20 11 0000 0002", "٠١٢٠٠٠٠٠٠٠٣"],
            "onboarding_completed": True,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["website"] == "https://littlestars.example"
    assert body["target_regions"] == [
        {"governorate": "Cairo", "cities": ["Nasr City", "Heliopolis"]},
        {"governorate": "Giza", "cities": []},
    ]
    assert body["working_days"] == [0, 1, 6]
    assert body["quiet_hours_start"] == "09:30"
    assert body["demo_whitelist"] == ["+201000000001", "+201100000002", "+201200000003"]
    assert body["onboarding_completed"] is True
    assert body["warnings"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"products": []},
        {"products": [PRODUCT] * 31},
        {"products": [{"name": ""}]},
        {"max_discount_percent": 51},
        {"max_discount_percent": -1},
        {"daily_send_cap": 0},
        {"daily_send_cap": 201},
        {"score_threshold": 0},
        {"score_threshold": 11},
        {"working_days": [7]},
        {"working_days": []},
        {"language": "fr"},
        {"tone": "rude"},
        {"autonomy_mode": "yolo"},
        {"target_regions": [{"governorate": "Atlantis"}]},
        {"target_regions": [{"governorate": "Cairo", "cities": ["Gotham"]}]},
        {"demo_whitelist": ["not a phone"]},
        {"demo_whitelist": [f"+20100000000{i}" for i in range(6)]},
        {"sequence_steps": []},
        {"sequence_steps": [{"day_offset": 0, "purpose": "followup", "template": "followup"}]},
        {
            "sequence_steps": [
                {"day_offset": 0, "purpose": "first_touch", "template": "intro"},
                {"day_offset": 0, "purpose": "followup", "template": "followup"},
            ]
        },
        {"sequence_steps": [{"day_offset": i, "purpose": "followup", "template": "f"} for i in range(5)]},
        {"company_name": None},
        {"unknown_field": 1},
    ],
)
async def test_invalid_values_are_rejected(client: AsyncClient, tenant: Tenant, body: dict[str, Any]) -> None:
    resp = await put(client, tenant, body)
    assert resp.status_code == 422, (body, resp.text)
    assert resp.json()["error"]["code"] == "validation_error"


async def test_quiet_hours_checked_against_stored_values(client: AsyncClient, tenant: Tenant) -> None:
    resp = await put(client, tenant, {"quiet_hours_start": "21:00"})  # stored end is 20:00
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_quiet_hours"
    assert (
        await put(client, tenant, {"quiet_hours_start": "21:00", "quiet_hours_end": "23:00"})
    ).status_code == 200


async def test_website_can_be_cleared(client: AsyncClient, tenant: Tenant) -> None:
    await put(client, tenant, {"website": "https://a.example"})
    assert (await put(client, tenant, {"website": None})).json()["website"] is None


async def test_onboarding_needs_the_basics(client: AsyncClient, tenant: Tenant) -> None:
    resp = await put(client, tenant, {"onboarding_completed": True})
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "onboarding_incomplete"
    assert "products" in error["message"]


async def test_send_cap_warning(client: AsyncClient, tenant: Tenant) -> None:
    body = (await put(client, tenant, {"daily_send_cap": 60})).json()
    assert "daily_send_cap_above_50" in body["warnings"]


async def test_members_cannot_change_settings(client: AsyncClient, tenant: Tenant) -> None:
    resp = await put(client, tenant, {"company_name": "x"}, role="member")
    assert resp.status_code == 403
    assert (await client.get("/api/v1/settings", headers=auth(tenant.id, "member"))).status_code == 200


async def test_tenant_isolation(client: AsyncClient, session: AsyncSession, tenant: Tenant) -> None:
    other = Tenant(name="Other")
    session.add(other)
    await session.flush()
    await put(client, tenant, {"company_name": "Tenant A only", "daily_send_cap": 5})
    body = (await client.get("/api/v1/settings", headers=auth(other.id))).json()
    assert body["company_name"] == ""
    assert body["daily_send_cap"] == 20


async def test_geo(client: AsyncClient, tenant: Tenant) -> None:
    body = (await client.get("/api/v1/settings/geo", headers=auth(tenant.id))).json()
    names = [g["name"] for g in body["governorates"]]
    assert len(names) == 27 and "Cairo" in names and "Aswan" in names
    cairo = next(g for g in body["governorates"] if g["name"] == "Cairo")
    assert cairo["name_ar"] == "القاهرة"
    assert {"name": "Nasr City", "name_ar": "مدينة نصر"} in cairo["cities"]
