"""P0-2: constraints and helpers on the models (unique dedupe key, one active insight, users, scoped)."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy import get_settings_for, scoped
from app.models.leads import Lead, LeadOutcome
from app.models.messaging import DemoRoute
from app.models.notifications import LearnedInsight
from app.models.tenants import Tenant, User


async def _tenant(session: AsyncSession, name: str = "T") -> Tenant:
    tenant = Tenant(name=name)
    session.add(tenant)
    await session.flush()
    return tenant


async def test_dedupe_key_unique_per_tenant(session: AsyncSession) -> None:
    a, b = await _tenant(session, "A"), await _tenant(session, "B")
    session.add_all(
        [
            Lead(tenant_id=a.id, name="x", dedupe_key="google_places:abc"),
            Lead(tenant_id=b.id, name="x", dedupe_key="google_places:abc"),  # another tenant: fine
        ]
    )
    await session.flush()
    nested = await session.begin_nested()
    session.add(Lead(tenant_id=a.id, name="y", dedupe_key="google_places:abc"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await nested.rollback()


async def test_ref_code_default_and_unique(session: AsyncSession) -> None:
    tenant = await _tenant(session)
    lead = Lead(tenant_id=tenant.id, name="x", dedupe_key="k1")
    session.add(lead)
    await session.flush()
    assert len(lead.ref_code) == 6
    assert not set(lead.ref_code) & set("0O1IL")


async def test_users_email_unique_and_lowercase(session: AsyncSession) -> None:
    tenant = await _tenant(session)
    session.add(User(tenant_id=tenant.id, email="owner@example.com", password_hash="h"))
    await session.flush()
    nested = await session.begin_nested()
    session.add(User(tenant_id=tenant.id, email="Owner@Example.com", password_hash="h"))
    with pytest.raises(IntegrityError):  # the CHECK (email = lower(email)) refuses it
        await session.flush()
    await nested.rollback()


async def test_one_active_insight_per_tenant(session: AsyncSession) -> None:
    tenant = await _tenant(session)
    session.add(LearnedInsight(tenant_id=tenant.id, version=1, insights=["a"], stats={}, is_active=True))
    await session.flush()
    nested = await session.begin_nested()
    session.add(LearnedInsight(tenant_id=tenant.id, version=2, insights=["b"], stats={}, is_active=True))
    with pytest.raises(IntegrityError):
        await session.flush()
    await nested.rollback()


async def test_outcome_check_and_demo_route_unique(session: AsyncSession) -> None:
    tenant = await _tenant(session)
    lead = Lead(tenant_id=tenant.id, name="x", dedupe_key="k")
    session.add(lead)
    await session.flush()
    nested = await session.begin_nested()
    session.add(LeadOutcome(tenant_id=tenant.id, lead_id=lead.id, outcome="maybe"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await nested.rollback()
    session.add(DemoRoute(tenant_id=tenant.id, test_phone="+201000000001", lead_id=lead.id))
    await session.flush()
    nested = await session.begin_nested()
    session.add(DemoRoute(tenant_id=tenant.id, test_phone="+201000000001", lead_id=lead.id))
    with pytest.raises(IntegrityError):
        await session.flush()
    await nested.rollback()


async def test_scoped_filters_by_tenant(session: AsyncSession) -> None:
    a, b = await _tenant(session, "A"), await _tenant(session, "B")
    session.add_all(
        [Lead(tenant_id=a.id, name="a", dedupe_key="1"), Lead(tenant_id=b.id, name="b", dedupe_key="2")]
    )
    await session.flush()
    names = (await session.execute(scoped(select(Lead.name), Lead, a.id))).scalars().all()
    assert names == ["a"]
    with pytest.raises(TypeError):
        scoped(select(Tenant), Tenant, uuid.uuid4())


async def test_get_settings_for_creates_defaults(session: AsyncSession) -> None:
    tenant = await _tenant(session)
    row = await get_settings_for(session, tenant.id)
    assert row.daily_send_cap == 20
    assert row.working_days == [0, 1, 2, 3, 5, 6]
    assert row.demo_mode is True and row.demo_whitelist == []
    assert row.sequence_steps[0]["purpose"] == "first_touch"
    assert (await get_settings_for(session, tenant.id)).id == row.id
