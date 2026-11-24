"""Tests for P2-4 leads list and stats endpoints."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.enums import LeadStatus
from app.models.leads import Lead
from app.models.tenants import Tenant, User


async def _seed_tenant_with_leads(session: AsyncSession) -> dict[str, str]:
    tenant = Tenant(name="Leads Test Co")
    session.add(tenant)
    await session.flush()
    user = User(
        tenant_id=tenant.id,
        email="leads-owner@example.com",
        password_hash="x",
        full_name="Owner",
        role="owner",
    )
    session.add(user)
    await session.flush()

    session.add_all(
        [
            Lead(
                tenant_id=tenant.id,
                name="Alexandria Tech Store",
                category="Computer Store",
                city="Smouha",
                governorate="Alexandria",
                status=LeadStatus.QUALIFIED.value,
                score=9,
                score_reasons=["Exact B2B fit", "High reviews"],
            ),
            Lead(
                tenant_id=tenant.id,
                name="Cairo Cafe",
                category="Cafe",
                city="Maadi",
                governorate="Cairo",
                status=LeadStatus.DISQUALIFIED.value,
                score=2,
                disqualify_reason="Not a hardware buyer",
            ),
        ]
    )
    await session.flush()
    token = create_access_token(user_id=user.id, tenant_id=tenant.id, role=user.role)
    return {"Cookie": f"access_token={token}"}


async def test_list_leads_filters_and_stats(client: AsyncClient, session: AsyncSession) -> None:
    headers = await _seed_tenant_with_leads(session)

    res = await client.get("/api/v1/leads?min_score=7&governorate=Alexandria", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Alexandria Tech Store"

    search_res = await client.get("/api/v1/leads?q=Cairo", headers=headers)
    assert search_res.status_code == 200
    assert search_res.json()["total"] == 1

    stats_res = await client.get("/api/v1/leads/stats", headers=headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total"] == 2
    assert stats["qualified_count"] == 1
    assert stats["avg_score"] == 5.5
