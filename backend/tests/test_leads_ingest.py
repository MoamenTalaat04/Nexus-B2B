"""P2-2: dedupe keys and ingest (normalize + dedupe → leads), including the no-N+1 guarantee."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import PlaceResult
from app.models.enums import ContactType
from app.models.leads import Contact, Lead
from app.models.tenants import Tenant
from app.services.leads_ingest import (
    dedupe_key,
    ingest_places,
    normalize_name,
    registrable_domain,
)


def place(i: int | str, **kw: Any) -> PlaceResult:
    data: dict[str, Any] = {
        "source": "google_places",
        "source_ref": f"place-{i}",
        "name": f"محل رقم {i}",
        "governorate": "Cairo",
        "city": "Nasr City",
        "phone_national": None,
        "website": None,
    }
    data.update(kw)
    return PlaceResult(**data)


@pytest.fixture
async def tenant(session: AsyncSession) -> Tenant:
    row = Tenant(name="Ingest")
    session.add(row)
    await session.flush()
    return row


@contextmanager
def count_queries(session: AsyncSession) -> Iterator[list[str]]:
    statements: list[str] = []
    engine = session.bind.sync_engine  # type: ignore[union-attr]

    def _count(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _count)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _count)


# ---------------------------------------------------------------------------------------------- keys


def test_key_priority() -> None:
    assert dedupe_key(place(1)) == "google_places:place-1"
    assert dedupe_key(place(1, source_ref="", phone_national="010 1234 5678")) == "mobile:+201012345678"
    assert dedupe_key(
        place(1, source_ref="", phone_national="02 2345 6789", website="https://www.shop.com.eg/ar")
    ) == ("domain:shop.com.eg")
    assert dedupe_key(place(1, source_ref="", name="محل أطفال", governorate="محافظة القاهرة")) == (
        "name:محل اطفال|cairo"
    )


def test_arabic_name_variants_share_a_key() -> None:
    variants = ["مكتبة الأمل للأطفال", "مكتبه الامل للاطفال", "مَكتبة الأمَل - للأطفال!", "مكتبة الإمل للأطفال"]
    keys = {dedupe_key(place(1, source_ref="", name=v)) for v in variants}
    assert len(keys) == 1
    assert normalize_name("بيبى لاند") == normalize_name("بيبي لاند")
    assert normalize_name("Kids  ZONE.") == "kids zone"


@pytest.mark.parametrize(
    ("url", "domain"),
    [
        ("https://www.LittleStars.com.eg/ar/home", "littlestars.com.eg"),
        ("shop.example.com", "example.com"),
        ("http://kids.co.uk", "kids.co.uk"),
        ("https://facebook.com/littlestars", None),
        ("https://www.instagram.com/x", None),
        ("https://wa.me/201012345678", None),
        ("https://mystore.business.site", None),
        ("http://127.0.0.1", None),
        ("not a url", None),
        ("", None),
        (None, None),
    ],
)
def test_registrable_domain(url: str | None, domain: str | None) -> None:
    assert registrable_domain(url) == domain


# ---------------------------------------------------------------------------------------------- ingest


async def test_same_place_twice_is_one_lead(session: AsyncSession, tenant: Tenant) -> None:
    first = await ingest_places(session, None, tenant.id, [place(1), place(2), place(1)], None)
    assert (first.created, first.duplicates) == (2, 1)
    second = await ingest_places(session, None, tenant.id, [place(1), place(3)], None)
    assert (second.created, second.duplicates) == (1, 1)
    count = len((await session.execute(select(Lead.id).where(Lead.tenant_id == tenant.id))).all())
    assert count == 3


async def test_same_mobile_under_two_place_ids(session: AsyncSession, tenant: Tenant) -> None:
    a = place("a", phone_national="010 1234 5678")
    b = place("b", phone_international="+20 10 1234 5678", name="فرع تاني")
    result = await ingest_places(session, None, tenant.id, [a, b], None)
    assert (result.created, result.duplicates) == (1, 1)
    # a mobile already known as a contact of another lead also counts
    lead = (await session.execute(select(Lead).where(Lead.tenant_id == tenant.id))).scalar_one()
    session.add(
        Contact(
            tenant_id=tenant.id,
            lead_id=lead.id,
            type=ContactType.MOBILE.value,
            value="+201198765432",
            source="manual",
        )
    )
    await session.flush()
    c = place("c", phone_national="01198765432")
    assert (await ingest_places(session, None, tenant.id, [c], None)).duplicates == 1


async def test_lead_fields(session: AsyncSession, tenant: Tenant) -> None:
    icp_id = uuid.uuid4()
    p = place(
        9,
        name="  روز كيدز  ",
        category="Children's clothing store",
        governorate="محافظة الجيزة",
        website="https://www.rosekids.com.eg",
        phone_national="010 1111 2222",
        rating=4.6,
        reviews_count=120,
        lat=30.0,
        lng=31.2,
        raw={"id": "place-9"},
    )
    result = await ingest_places(session, None, tenant.id, [p], icp_id)
    lead = await session.get(Lead, result.lead_ids[0])
    assert lead is not None
    assert lead.name == "روز كيدز"
    assert lead.status == "new"
    assert lead.governorate == "Giza"
    assert lead.domain == "rosekids.com.eg"
    assert lead.icp_version_id == icp_id
    assert lead.dedupe_key == "google_places:place-9"
    assert lead.raw["phone_e164"] == "+201011112222"
    assert lead.raw["raw"] == {"id": "place-9"}
    assert len(lead.ref_code) == 6


async def test_closed_places_are_skipped(session: AsyncSession, tenant: Tenant) -> None:
    result = await ingest_places(
        session, None, tenant.id, [place(1, business_status="CLOSED_PERMANENTLY"), place(2)], None
    )
    assert (result.created, result.skipped) == (1, 1)


async def test_limit(session: AsyncSession, tenant: Tenant) -> None:
    result = await ingest_places(session, None, tenant.id, [place(i) for i in range(10)], None, limit=4)
    assert result.created == 4


async def test_tenant_isolation(session: AsyncSession, tenant: Tenant) -> None:
    other = Tenant(name="Other")
    session.add(other)
    await session.flush()
    await ingest_places(session, None, tenant.id, [place(1)], None)
    result = await ingest_places(session, None, other.id, [place(1)], None)
    assert result.created == 1  # the same place is a new lead for another tenant


async def test_no_n_plus_one(session: AsyncSession, tenant: Tenant) -> None:
    await ingest_places(session, None, tenant.id, [place(i) for i in range(5)], None)
    places = [place(i, phone_national=f"0101234{i:04d}") for i in range(60)]
    with count_queries(session) as statements:
        result = await ingest_places(session, None, tenant.id, places, None)
    assert result.created == 55 and result.duplicates == 5
    # 3 preload queries (keys, ingest phones, contact phones) + 1 bulk INSERT, whatever the batch size
    assert len(statements) <= 4, statements
