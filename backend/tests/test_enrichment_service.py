import asyncio
import uuid

import pytest

from app.adapters import registry
from app.adapters.base import ContactCandidate
from app.models.enums import ContactType, LeadStatus, StepType
from app.models.leads import Lead
from app.services import enrichment


class _FakeRun:
    def __init__(self) -> None:
        self.steps: list[dict] = []

    async def step(self, step_type: StepType, name: str, **kwargs: object) -> None:
        self.steps.append({"type": step_type, "name": name, **kwargs})


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, row: object) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        return None


def _lead(status: LeadStatus = LeadStatus.QUALIFIED) -> Lead:
    return Lead(
        tenant_id=uuid.uuid4(),
        name="Test Kids Shop",
        website="https://example.com",
        status=status.value,
        raw={
            "phone_e164": "+201012345678",
            "phone_national": "01012345678",
        },
        dedupe_key=f"k-{uuid.uuid4()}",
    )


class _ConcurrentEnricher:
    def __init__(self, name: str, delay: float, candidates: list[ContactCandidate]) -> None:
        self.name = name
        self.delay = delay
        self.candidates = candidates

    async def enrich(
        self,
        *,
        lead_name: str,
        website: str | None,
        known: list[ContactCandidate],
    ) -> list[ContactCandidate]:
        await asyncio.sleep(self.delay)
        return self.candidates


@pytest.mark.asyncio
async def test_enrich_lead_upserts_primary_and_transitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lead = _lead()
    session = _FakeSession()
    run = _FakeRun()

    enrichers = [
        _ConcurrentEnricher(
            "places",
            0.01,
            [
                ContactCandidate(
                    type=ContactType.MOBILE,
                    value="+201012345678",
                    source="google_places",
                    confidence=0.9,
                )
            ],
        ),
        _ConcurrentEnricher(
            "website",
            0,
            [
                ContactCandidate(
                    type=ContactType.MOBILE,
                    value="+201012345678",
                    source="website",
                    confidence=0.95,
                ),
                ContactCandidate(
                    type=ContactType.WHATSAPP_LINK,
                    value="https://wa.me/201012345678",
                    source="website",
                    confidence=0.95,
                ),
                ContactCandidate(
                    type=ContactType.EMAIL,
                    value="sales@example.com",
                    source="website",
                    confidence=0.6,
                ),
            ],
        ),
    ]

    async def no_existing(session: _FakeSession, lead: Lead) -> list:
        return []

    monkeypatch.setattr(registry, "get_enrichers", lambda: enrichers)
    monkeypatch.setattr(enrichment, "_existing_contacts", no_existing)

    contacts = await enrichment.enrich_lead(session, run, lead)

    assert len({(row.type, row.value) for row in contacts}) >= 3
    mobile = next(row for row in contacts if row.type == ContactType.MOBILE.value)
    assert mobile.is_primary is True
    assert mobile.confidence == 0.95
    assert mobile.source == "website"
    assert lead.status == LeadStatus.ENRICHED.value
    assert len([step for step in run.steps if step["type"] == StepType.EXTERNAL_API]) == 2


@pytest.mark.asyncio
async def test_enrich_lead_no_mobile_transitions_no_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lead = _lead()
    lead.raw = {}
    session = _FakeSession()
    run = _FakeRun()

    monkeypatch.setattr(
        registry,
        "get_enrichers",
        lambda: [
            _ConcurrentEnricher(
                "website",
                0,
                [
                    ContactCandidate(
                        type=ContactType.EMAIL,
                        value="sales@example.com",
                        source="website",
                        confidence=0.6,
                    )
                ],
            )
        ],
    )

    async def no_existing(session: _FakeSession, lead: Lead) -> list:
        return []

    monkeypatch.setattr(enrichment, "_existing_contacts", no_existing)

    contacts = await enrichment.enrich_lead(session, run, lead)

    assert [row.type for row in contacts] == [ContactType.EMAIL.value]
    assert lead.status == LeadStatus.NO_CONTACT.value


@pytest.mark.asyncio
async def test_enrichers_run_concurrently(monkeypatch: pytest.MonkeyPatch) -> None:
    lead = _lead()
    session = _FakeSession()
    run = _FakeRun()
    active = 0
    peak = 0

    class Concurrent:
        def __init__(self, name: str) -> None:
            self.name = name

        async def enrich(self, **kwargs: object) -> list[ContactCandidate]:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.02)
            active -= 1
            return []

    monkeypatch.setattr(
        registry,
        "get_enrichers",
        lambda: [Concurrent("places"), Concurrent("website")],
    )

    async def no_existing(session: _FakeSession, lead: Lead) -> list:
        return []

    monkeypatch.setattr(enrichment, "_existing_contacts", no_existing)

    await enrichment.enrich_lead(session, run, lead)

    assert peak == 2
    assert len([step for step in run.steps if step["type"] == StepType.EXTERNAL_API]) == 2
