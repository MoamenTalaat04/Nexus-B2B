"""Lead contact enrichment service (P3-1)."""

import asyncio
import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import registry
from app.adapters.base import ContactCandidate
from app.core import lead_state
from app.core.phones import is_eg_mobile, normalize_eg_phone
from app.core.tracing import RunContext
from app.models.enums import ContactType, LeadStatus, StepType
from app.models.leads import Contact, Lead

logger = logging.getLogger("app.services.enrichment")

VALID_CONTACT_SOURCES = {"google_places", "website", "manual", "lead_initiated"}


def _candidate_key(candidate: ContactCandidate) -> tuple[ContactType, str]:
    if candidate.type in (ContactType.MOBILE, ContactType.LANDLINE):
        normalized = normalize_eg_phone(candidate.value)
        if normalized:
            return candidate.type, normalized
    return candidate.type, candidate.value.strip()


def _known_candidates(session: AsyncSession, lead: Lead) -> list[ContactCandidate]:
    known: list[ContactCandidate] = []
    raw = lead.raw if isinstance(lead.raw, dict) else {}
    for key in ("phone_e164", "phone_international", "phone_national"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            known.append(
                ContactCandidate(
                    type=ContactType.MOBILE,
                    value=value,
                    source="google_places",
                    confidence=0.9,
                )
            )
    return known


def _safe_source(source: str) -> str:
    return source if source in VALID_CONTACT_SOURCES else "website"


async def _existing_contacts(
    session: AsyncSession,
    lead: Lead,
) -> list[Contact]:
    rows = (
        (
            await session.execute(
                select(Contact)
                .where(Contact.tenant_id == lead.tenant_id, Contact.lead_id == lead.id)
                .order_by(Contact.created_at.asc(), Contact.id.asc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


def _contact_candidate(row: Contact) -> ContactCandidate:
    return ContactCandidate(
        type=ContactType(row.type),
        value=row.value,
        source=_safe_source(row.source),
        confidence=float(row.confidence),
    )


def _linked_mobile_values(candidates: dict[tuple[ContactType, str], ContactCandidate]) -> set[str]:
    linked: set[str] = set()
    for (contact_type, value), _candidate in candidates.items():
        if contact_type != ContactType.WHATSAPP_LINK:
            continue
        phone_matches = re.findall(r"(?:wa\.me/|phone=)([0-9+]+)", value, re.IGNORECASE)
        for phone_match in phone_matches:
            normalized = normalize_eg_phone(phone_match)
            if normalized and is_eg_mobile(normalized):
                linked.add(normalized)
    return linked


async def enrich_lead(
    session: AsyncSession,
    run: RunContext,
    lead: Lead,
    *,
    db_lock: asyncio.Lock | None = None,
) -> list[Contact]:
    """Run all configured enrichers and persist tenant-scoped contacts.

    The enrichers (network) may run for several leads at once, but one AsyncSession allows only one operation
    at a time: callers that enrich leads concurrently on the same session pass a shared `db_lock`, which
    guards every database read and write below.
    """
    lock = db_lock or asyncio.Lock()
    enrichers = registry.get_enrichers()
    async with lock:
        existing = await _existing_contacts(session, lead)
    merged: dict[tuple[ContactType, str], ContactCandidate] = {}

    for row in existing:
        candidate = _contact_candidate(row)
        key = _candidate_key(candidate)
        previous = merged.get(key)
        if previous is None or candidate.confidence > previous.confidence:
            merged[key] = candidate

    known = _known_candidates(session, lead)
    for row in existing:
        if row.type in (ContactType.MOBILE.value, ContactType.LANDLINE.value):
            known.append(
                ContactCandidate(
                    type=ContactType(row.type),
                    value=row.value,
                    source=_safe_source(row.source),
                    confidence=float(row.confidence),
                )
            )

    async def run_enricher(enricher: Any) -> list[ContactCandidate]:
        name = str(getattr(enricher, "name", enricher.__class__.__name__))
        started = __import__("time").perf_counter()
        try:
            candidates = await enricher.enrich(
                lead_name=lead.name,
                website=lead.website,
                known=known,
            )
            latency_ms = int((__import__("time").perf_counter() - started) * 1000)
            await run.step(
                StepType.EXTERNAL_API,
                f"{name}.enrich",
                input={"lead_name": lead.name, "has_website": bool(lead.website)},
                output={"candidate_count": len(candidates)},
                latency_ms=latency_ms,
                lead_id=lead.id,
            )
            return candidates
        except Exception as exc:
            latency_ms = int((__import__("time").perf_counter() - started) * 1000)
            await run.step(
                StepType.EXTERNAL_API,
                f"{name}.enrich",
                input={"lead_name": lead.name, "has_website": bool(lead.website)},
                output={"candidate_count": 0, "error": type(exc).__name__},
                latency_ms=latency_ms,
                lead_id=lead.id,
            )
            logger.exception("enrichment enricher %s failed for lead %s", name, lead.id)
            return []

    enricher_results = await asyncio.gather(*(run_enricher(enricher) for enricher in enrichers))
    for candidates in enricher_results:
        for candidate in candidates:
            key = _candidate_key(candidate)
            previous = merged.get(key)
            if previous is None or candidate.confidence > previous.confidence:
                merged[key] = candidate

    linked_mobiles = _linked_mobile_values(merged)
    existing_by_key = {_candidate_key(_contact_candidate(row)): row for row in existing}

    winners: dict[ContactType, tuple[tuple[bool, float], tuple[ContactType, str], ContactCandidate]] = {}
    for key, candidate in merged.items():
        contact_type, value = key
        whatsapp_preferred = contact_type == ContactType.MOBILE and value in linked_mobiles
        rank = (whatsapp_preferred, candidate.confidence)
        previous_winner = winners.get(contact_type)
        if previous_winner is None or rank > previous_winner[0]:
            winners[contact_type] = (rank, key, candidate)

    async with lock:
        persisted: list[Contact] = []
        for key, candidate in merged.items():
            contact_type, value = key
            source = _safe_source(candidate.source)
            existing_row = existing_by_key.get(key)
            winner = winners.get(contact_type)
            is_primary = bool(winner and winner[1] == key)

            if existing_row is not None:
                existing_row.source = source
                existing_row.confidence = candidate.confidence
                existing_row.is_primary = is_primary
                persisted.append(existing_row)
            else:
                row = Contact(
                    tenant_id=lead.tenant_id,
                    lead_id=lead.id,
                    type=contact_type.value,
                    value=value,
                    source=source,
                    is_primary=is_primary,
                    confidence=candidate.confidence,
                )
                session.add(row)
                persisted.append(row)

        await session.flush()

        has_mobile = any(
            contact.type == ContactType.MOBILE.value for contact in persisted if contact.is_primary
        )
        if has_mobile:
            await lead_state.transition(
                session,
                lead,
                LeadStatus.ENRICHED,
                reason="mobile contact found",
                actor="agent",
            )
        else:
            await lead_state.transition(
                session,
                lead,
                LeadStatus.NO_CONTACT,
                reason="no mobile number found",
                actor="agent",
            )

        await session.flush()
    return persisted
