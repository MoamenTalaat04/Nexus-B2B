import uuid
from datetime import datetime

import pytest

from app.models.enums import AgentRunKind, LeadStatus, StepType
from app.workers.jobs import enrichment as enrichment_job


class _FakeRun:
    def __init__(self) -> None:
        self.output_summary: dict | None = None
        self.steps: list[dict] = []

    async def step(self, step_type: StepType, name: str, **kwargs: object) -> None:
        self.steps.append({"type": step_type, "name": name, **kwargs})


class _FakeLead:
    def __init__(self, lead_id: uuid.UUID, status: LeadStatus) -> None:
        self.id = lead_id
        self.status = status.value
        self.next_action_at: datetime | None = None


class _FakeRows:
    def __init__(self, rows: list[_FakeLead]) -> None:
        self.rows = rows

    def scalars(self) -> "_FakeRows":
        return self

    def all(self) -> list[_FakeLead]:
        return self.rows


class _FakeSession:
    def __init__(self, leads: list[_FakeLead]) -> None:
        self.leads = leads
        self.commits = 0

    async def execute(self, _: object) -> _FakeRows:
        return _FakeRows(self.leads)

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_run_enrich_leads_creates_enrichment_run_and_sets_next_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    enriched = _FakeLead(uuid.uuid4(), LeadStatus.ENRICHED)
    no_contact = _FakeLead(uuid.uuid4(), LeadStatus.NO_CONTACT)
    session = _FakeSession([enriched, no_contact])
    run = _FakeRun()
    agent_args: dict[str, object] = {}

    async def fake_enrich_lead(session: object, ctx: object, lead: _FakeLead, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(enrichment_job, "enrich_lead", fake_enrich_lead)

    # The real agent_run is asynccontextmanager; a direct lambda wrapper cannot be awaited here.
    # This test deliberately uses a small context helper when verifying next-action behavior.
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_context(*args: object, **kwargs: object):
        agent_args["args"] = args
        agent_args["kwargs"] = kwargs
        yield run

    monkeypatch.setattr(enrichment_job, "agent_run", fake_context)

    summary = await enrichment_job.run_enrich_leads(
        session,
        tenant_id,
        [enriched.id, no_contact.id],
    )

    assert summary == {"processed": 2, "enriched": 1, "no_contact": 1, "failed": 0}
    assert enriched.next_action_at is not None
    assert no_contact.next_action_at is None
    assert session.commits == 1
    assert agent_args["args"][1] == AgentRunKind.ENRICHMENT
    assert agent_args["kwargs"]["trigger"] == "chained"


@pytest.mark.asyncio
async def test_run_enrich_leads_isolates_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    first = _FakeLead(uuid.uuid4(), LeadStatus.ENRICHED)
    second = _FakeLead(uuid.uuid4(), LeadStatus.NO_CONTACT)
    session = _FakeSession([first, second])
    run = _FakeRun()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_context(*args: object, **kwargs: object):
        yield run

    monkeypatch.setattr(enrichment_job, "agent_run", fake_context)

    async def fake_enrich_lead(session: object, ctx: object, lead: _FakeLead, **kwargs: object) -> None:
        if lead is first:
            raise RuntimeError("one lead failed")

    monkeypatch.setattr(enrichment_job, "enrich_lead", fake_enrich_lead)

    summary = await enrichment_job.run_enrich_leads(
        session,
        tenant_id,
        [first.id, second.id],
    )

    assert summary == {"processed": 1, "enriched": 0, "no_contact": 1, "failed": 1}
    assert first.next_action_at is None
    assert second.next_action_at is None
