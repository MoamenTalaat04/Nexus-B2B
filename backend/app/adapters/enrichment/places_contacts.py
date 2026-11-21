"""Places contacts enricher (P3-1)."""

from app.adapters.base import ContactCandidate
from app.core.phones import is_eg_mobile, normalize_eg_phone
from app.models.enums import ContactType


class PlacesContactsEnricher:
    name = "places_contacts"

    async def enrich(
        self,
        *,
        lead_name: str,
        website: str | None,
        known: list[ContactCandidate],
    ) -> list[ContactCandidate]:
        candidates: list[ContactCandidate] = []
        seen: set[tuple[ContactType, str]] = set()

        for candidate in known:
            normalized = normalize_eg_phone(candidate.value)
            if normalized is None:
                continue
            contact_type = ContactType.MOBILE if is_eg_mobile(normalized) else ContactType.LANDLINE
            key = (contact_type, normalized)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                ContactCandidate(
                    type=contact_type,
                    value=normalized,
                    source="google_places",
                    confidence=0.9,
                )
            )
        return candidates
