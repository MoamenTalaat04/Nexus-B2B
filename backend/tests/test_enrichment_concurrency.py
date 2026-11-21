"""Regression test: job_enrich_leads enriches several leads at once on ONE real AsyncSession.

The first real chain run failed one lead with "Session is already flushing": leads ran concurrently and their
database work interleaved on the shared session. The DB part is now guarded by a lock; the network part
(the enrichers) still runs in parallel.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import registry
from app.adapters.base import ContactCandidate
from app.core import lead_state
from app.models.enums import ContactType, LeadStatus
from app.models.leads import Contact, Lead
from app.models.tenants import Tenant
from app.workers.jobs import enrichment as enrichment_job


class _Run:
    async def step(self, *args: Any, **kwargs: Any) -> None:  # tracing has its own session in production
        return None


class _SlowEnricher:
    """Returns one mobile per lead after a short, lead-specific delay, so the leads finish out of order."""

    name = "slow"

    async def enrich(
        self, *, lead_name: str, website: str | None, known: list[ContactCandidate]
    ) -> list[ContactCandidate]:
        n = int(lead_name.rsplit(" ", 1)[1])
        await asyncio.sleep(0.002 * ((n * 7) % 5))
        return [
            ContactCandidate(
                type=ContactType.MOBILE, value=f"+20100000{n:04d}", source="website", confidence=0.85
            ),
            ContactCandidate(
                type=ContactType.EMAIL, value=f"shop{n}@example.com", source="website", confidence=0.6
            ),
        ]


async def test_concurrent_leads_share_one_session_safely(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = Tenant(name="Enrichment concurrency")
    session.add(tenant)
    await session.flush()
    leads = []
    for n in range(12):
        lead = Lead(tenant_id=tenant.id, name=f"Kids shop {n}", dedupe_key=f"conc-{uuid.uuid4()}")
        session.add(lead)
        await session.flush()
        await lead_state.transition(session, lead, LeadStatus.QUALIFIED, reason="test", actor="agent")
        leads.append(lead)
    await session.commit()

    @asynccontextmanager
    async def fake_agent_run(*args: Any, **kwargs: Any) -> AsyncIterator[_Run]:
        yield _Run()

    monkeypatch.setattr(enrichment_job, "agent_run", fake_agent_run)
    monkeypatch.setattr(registry, "get_enrichers", lambda: [_SlowEnricher()])

    summary = await enrichment_job.run_enrich_leads(session, tenant.id, [lead.id for lead in leads])

    assert summary == {"processed": 12, "enriched": 12, "no_contact": 0, "failed": 0}
    for lead in leads:
        await session.refresh(lead)
        assert lead.status == LeadStatus.ENRICHED.value
        assert lead.next_action_at is not None
    primary_mobiles = await session.scalar(
        select(func.count())
        .select_from(Contact)
        .where(Contact.tenant_id == tenant.id, Contact.type == ContactType.MOBILE.value, Contact.is_primary)
    )
    assert primary_mobiles == 12
