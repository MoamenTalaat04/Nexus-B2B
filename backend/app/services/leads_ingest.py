"""Normalize + dedupe search results into leads (P2-2, ARCHITECTURE section 3: "normalize + dedupe").

dedupe_key(place), in priority order:
  1. "<source>:<source_ref>"            e.g. "google_places:ChIJ…" (the same place found again)
  2. "mobile:+2010…"                    the place's phone, when it is an Egyptian mobile
  3. "domain:littlestars.com.eg"        the registrable domain of its website (not social/link hosts)
  4. "name:<normalized name>|<governorate>"
A second check catches chains and re-listed shops: the same normalized mobile already on another lead (in its
contacts or in the phone stored at ingest) counts as a duplicate even when the place id differs.

Leads are inserted with one bulk INSERT … ON CONFLICT DO NOTHING (the unique (tenant_id, dedupe_key)
constraint is the final guard against a concurrent run), after one query that preloads the tenant's keys.
`leads.raw` holds the whole PlaceResult as JSON (phones, types, business_status and Google's own payload under
"raw") plus "phone_e164", so enrichment (P3-1) can turn the phone into a contact without calling Google again.
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import PlaceResult
from app.core.geo_eg_coords import find_governorate, normalize_arabic
from app.core.phones import is_eg_mobile, normalize_eg_phone
from app.core.refcodes import new_ref_code
from app.core.tracing import RunContext
from app.models.enums import ContactType, LeadStatus
from app.models.leads import Contact, Lead

CLOSED_STATUSES = {"CLOSED_PERMANENTLY"}

# Websites that are not the business's own domain (a Facebook page is not "facebook.com" the business).
NON_BUSINESS_HOSTS = {
    "facebook.com",
    "fb.com",
    "instagram.com",
    "wa.me",
    "whatsapp.com",
    "linktr.ee",
    "google.com",
    "goo.gl",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "jumia.com.eg",
    "amazon.eg",
    "talabat.com",
    "bit.ly",
    "blogspot.com",
    "wixsite.com",
    "business.site",
    "sites.google.com",
}
# Second-level public suffixes common for Egyptian/regional businesses (no tldextract dependency).
TWO_LEVEL_SUFFIXES = {
    "com.eg",
    "org.eg",
    "net.eg",
    "edu.eg",
    "gov.eg",
    "sci.eg",
    "co.uk",
    "com.sa",
    "com.tr",
    "co.ae",
    "com.cn",
}

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_name(text: str) -> str:
    """Arabic-aware compare form: no diacritics/tatweel, أ/إ/آ→ا, ة→ه, ى→ي, lowercase, no punctuation."""
    s = normalize_arabic(text)
    s = _PUNCT_RE.sub(" ", s).replace("_", " ")
    return _SPACE_RE.sub(" ", s).strip()


def registrable_domain(website: str | None) -> str | None:
    """ "https://www.Shop.com.eg/ar/home" → "shop.com.eg"; social/link hosts and junk → None."""
    if not website or not website.strip():
        return None
    url = website.strip()
    if "://" not in url:
        url = "http://" + url
    try:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return None
    if not host or "." not in host or re.fullmatch(r"[\d.]+", host):
        return None
    host = host.removeprefix("www.")
    labels = host.split(".")
    suffix2 = ".".join(labels[-2:])
    domain = ".".join(labels[-3:]) if suffix2 in TWO_LEVEL_SUFFIXES and len(labels) >= 3 else suffix2
    if domain in NON_BUSINESS_HOSTS or host in NON_BUSINESS_HOSTS:
        return None
    return domain


def place_mobile(place: PlaceResult) -> str | None:
    for raw in (place.phone_international, place.phone_national):
        e164 = normalize_eg_phone(raw)
        if e164 and is_eg_mobile(e164):
            return e164
    return None


def place_phone(place: PlaceResult) -> str | None:
    """Any valid Egyptian phone (mobile preferred), E.164."""
    return place_mobile(place) or normalize_eg_phone(place.phone_international or place.phone_national)


def canonical_governorate(place: PlaceResult) -> str | None:
    found = find_governorate(place.governorate)
    return found.name if found else place.governorate


def dedupe_key(place: PlaceResult) -> str:
    if place.source_ref:
        return f"{place.source}:{place.source_ref}"
    mobile = place_mobile(place)
    if mobile:
        return f"mobile:{mobile}"
    domain = registrable_domain(place.website)
    if domain:
        return f"domain:{domain}"
    governorate = normalize_name(canonical_governorate(place) or "")
    return f"name:{normalize_name(place.name)}|{governorate}"


@dataclass
class IngestResult:
    created: int = 0
    duplicates: int = 0
    skipped: int = 0  # closed permanently / unusable
    lead_ids: list[uuid.UUID] = field(default_factory=list)


async def _existing_keys(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[set[str], set[str]]:
    """(dedupe keys, known mobiles) for the tenant, in two queries."""
    keys = set(
        (
            await session.execute(
                select(Lead.dedupe_key).where(Lead.tenant_id == tenant_id, Lead.dedupe_key.is_not(None))
            )
        ).scalars()
    )
    ingest_phones = (
        await session.execute(
            select(Lead.raw["phone_e164"].astext).where(
                Lead.tenant_id == tenant_id, Lead.raw["phone_e164"].astext.is_not(None)
            )
        )
    ).scalars()
    contact_phones = (
        await session.execute(
            select(Contact.value).where(
                Contact.tenant_id == tenant_id, Contact.type == ContactType.MOBILE.value
            )
        )
    ).scalars()
    mobiles = {p for p in ingest_phones if p and is_eg_mobile(p)} | {p for p in contact_phones if p}
    return {k for k in keys if k}, mobiles


def _row(
    place: PlaceResult,
    *,
    tenant_id: uuid.UUID,
    key: str,
    run: RunContext | None,
    icp_version_id: uuid.UUID | None,
) -> dict[str, Any]:
    raw = place.model_dump(mode="json")
    raw["phone_e164"] = place_phone(place)
    return {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "source": place.source,
        "source_ref": place.source_ref or None,
        "name": place.name.strip()[:300],
        "category": place.category,
        "address": place.address,
        "city": place.city,
        "governorate": canonical_governorate(place),
        "lat": place.lat,
        "lng": place.lng,
        "website": place.website,
        "domain": registrable_domain(place.website),
        "google_maps_url": place.google_maps_url,
        "rating": place.rating,
        "reviews_count": place.reviews_count,
        "raw": raw,
        "status": LeadStatus.NEW.value,
        "icp_version_id": icp_version_id,
        "sourcing_run_id": run.run_id if run else None,
        "ref_code": new_ref_code(),
        "dedupe_key": key,
    }


async def ingest_places(
    session: AsyncSession,
    run: RunContext | None,
    tenant_id: uuid.UUID,
    places: list[PlaceResult],
    icp_version_id: uuid.UUID | None,
    *,
    limit: int | None = None,
) -> IngestResult:
    """Create status=new leads for the places that are not already known (flushed, not committed).

    `limit` caps how many leads are created from this batch (the sourcing job's max_results budget).
    """
    result = IngestResult()
    keys, mobiles = await _existing_keys(session, tenant_id)
    rows: list[dict[str, Any]] = []
    for place in places:
        if (place.business_status or "").upper() in CLOSED_STATUSES or not place.name.strip():
            result.skipped += 1
            continue
        key = dedupe_key(place)
        mobile = place_mobile(place)
        if key in keys or (mobile and mobile in mobiles):
            result.duplicates += 1
            continue
        if limit is not None and len(rows) >= limit:
            break
        keys.add(key)
        if mobile:
            mobiles.add(mobile)
        rows.append(_row(place, tenant_id=tenant_id, key=key, run=run, icp_version_id=icp_version_id))
    if rows:
        stmt = pg_insert(Lead).values(rows).on_conflict_do_nothing().returning(Lead.id)
        inserted = list((await session.execute(stmt)).scalars())
        result.created = len(inserted)
        result.duplicates += len(rows) - len(inserted)  # lost a race with another run
        result.lead_ids = inserted
        await session.flush()
    return result
