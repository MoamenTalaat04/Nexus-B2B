"""Deterministic mock contact enrichment."""

import hashlib

from app.adapters.base import ContactCandidate
from app.models.enums import ContactType


class MockEnricher:
    name = "mock_enricher"

    async def enrich(
        self,
        *,
        lead_name: str,
        website: str | None,
        known: list[ContactCandidate],
    ) -> list[ContactCandidate]:
        digest = hashlib.sha256(lead_name.strip().lower().encode()).digest()
        if digest[0] % 2:
            suffix = int.from_bytes(digest[:4], "big") % 100000000
            prefixes = ("10", "11", "12", "15")
            prefix = prefixes[digest[4] % len(prefixes)]
            return [
                ContactCandidate(
                    type=ContactType.MOBILE,
                    value=f"+20{prefix}{suffix:08d}",
                    source="mock",
                    confidence=0.8,
                )
            ]
        return []
