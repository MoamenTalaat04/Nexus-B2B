import asyncio
import json
import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core import tracing
from app.core.tracing import agent_run, create_queued_run, mask_phones, safe_payload
from app.models.enums import AgentRunKind, AgentRunStatus, StepType
from app.models.runs import AgentRun, AgentStep
from app.models.tenants import Tenant


@pytest.fixture
async def tenant(session: AsyncSession) -> Tenant:
    t = Tenant(name="Tracing test")
    session.add(t)
    await session.flush()
    return t


async def _run(session: AsyncSession, run_id: uuid.UUID) -> AgentRun:
    stmt = select(AgentRun).where(AgentRun.id == run_id).execution_options(populate_existing=True)
    return (await session.execute(stmt)).scalar_one()


async def _steps(session: AsyncSession, run_id: uuid.UUID) -> list[AgentStep]:
    stmt = (
        select(AgentStep)
        .where(AgentStep.run_id == run_id)
        .order_by(AgentStep.seq)
        .execution_options(populate_existing=True)
    )
    return list((await session.execute(stmt)).scalars())


async def test_successful_run_records_steps_and_totals(session: AsyncSession, tenant: Tenant) -> None:
    async with agent_run(tenant.id, AgentRunKind.SCORING, trigger="manual", input={"n": 3}) as run:
        await run.step(StepType.LLM_CALL, "a", model="m", input_tokens=100, output_tokens=20, cost_usd=0.0012)
        await run.step(StepType.LLM_CALL, "b", model="m", input_tokens=50, output_tokens=10, cost_usd=0.0003)
        await run.step(StepType.DECISION, "threshold", output={"qualified": 2})
        run.output_summary = {"qualified": 2}

    row = await _run(session, run.run_id)
    assert row.status == AgentRunStatus.SUCCEEDED
    assert row.kind == "scoring" and row.trigger == "manual" and row.input == {"n": 3}
    assert row.started_at is not None and row.finished_at is not None
    assert (row.total_input_tokens, row.total_output_tokens) == (150, 30)
    assert float(row.total_cost_usd) == pytest.approx(0.0015)
    assert row.output_summary == {"qualified": 2}
    steps = await _steps(session, run.run_id)
    assert [s.seq for s in steps] == [1, 2, 3]
    assert [s.step_type for s in steps] == ["llm_call", "llm_call", "decision"]


async def test_failure_marks_run_failed_records_error_and_reraises(
    session: AsyncSession, tenant: Tenant
) -> None:
    with pytest.raises(ValueError, match="boom"):
        async with agent_run(tenant.id, AgentRunKind.SOURCING, trigger="schedule", input={}) as run:
            await run.step(StepType.EXTERNAL_API, "places.search")
            raise ValueError("boom")

    row = await _run(session, run.run_id)
    assert row.status == AgentRunStatus.FAILED
    assert row.error == "ValueError: boom"
    steps = await _steps(session, run.run_id)
    assert steps[-1].step_type == StepType.ERROR
    assert steps[-1].output == {"error": "ValueError: boom"}


async def test_cancelled_run_is_marked_cancelled(session: AsyncSession, tenant: Tenant) -> None:
    with pytest.raises(asyncio.CancelledError):
        async with agent_run(tenant.id, AgentRunKind.REPLY, trigger="webhook", input={}) as run:
            raise asyncio.CancelledError()
    assert (await _run(session, run.run_id)).status == AgentRunStatus.CANCELLED


async def test_big_payloads_are_truncated(session: AsyncSession, tenant: Tenant) -> None:
    async with agent_run(tenant.id, AgentRunKind.ENRICHMENT, trigger="manual", input={}) as run:
        await run.step(StepType.EXTERNAL_API, "fetch", input={"html": "ا" * 30_000}, output="x" * 50)
    step = (await _steps(session, run.run_id))[0]
    assert step.input["_truncated"] is True
    assert step.input["_original_bytes"] > 20 * 1024
    assert len(json.dumps(step.input, ensure_ascii=False).encode()) <= 20 * 1024
    assert step.output == "x" * 50


def test_mask_phones_keeps_last_three_digits() -> None:
    assert mask_phones("+201012345678") == "+*********678"
    assert mask_phones("call 0101 234 5678 now") == "call **** *** *678 now"
    # Dates, UUIDs, short numbers and prices stay readable.
    untouched = "on 2026-11-18, id 3f1c2a9e-1234-4567-8901-234567890123, 250 EGP, order 12345"
    assert mask_phones(untouched) == untouched


def test_safe_payload_masks_nested_values_and_handles_models() -> None:
    from pydantic import BaseModel

    class Lead(BaseModel):
        phone: str
        name: str

    data = safe_payload({"leads": [Lead(phone="01012345678", name="Shop")], "n": 1})
    assert data == {"leads": [{"phone": "********678", "name": "Shop"}], "n": 1}


async def test_queued_run_is_reused(session: AsyncSession, tenant: Tenant) -> None:
    run_id = await create_queued_run(
        session, tenant.id, AgentRunKind.ICP_BUILD, trigger="manual", input={"x": 1}
    )
    assert (await _run(session, run_id)).status == AgentRunStatus.QUEUED

    async with agent_run(tenant.id, AgentRunKind.ICP_BUILD, trigger="manual", input={}, run_id=run_id) as run:
        assert run.run_id == run_id
    row = await _run(session, run_id)
    assert row.status == AgentRunStatus.SUCCEEDED
    assert row.input == {"x": 1}
    count = await session.scalar(
        select(func.count()).select_from(AgentRun).where(AgentRun.tenant_id == tenant.id)
    )
    assert count == 1


async def test_trace_survives_rollback_of_the_job_session(engine: AsyncEngine) -> None:
    """Uses real, separate transactions (not the per-test rollback session) and cleans up after itself."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        t = Tenant(name="Rollback test")
        s.add(t)
        await s.commit()
    tracing.use_session_factory(factory)
    try:
        async with factory() as job_session:
            async with agent_run(t.id, AgentRunKind.SCORING, trigger="manual", input={}) as run:
                job_session.add(Tenant(name="should be rolled back"))
                await job_session.flush()
                await run.step(StepType.DECISION, "kept")
            await job_session.rollback()

        async with factory() as check:
            steps = list(
                (await check.execute(select(AgentStep).where(AgentStep.run_id == run.run_id))).scalars()
            )
            assert [s.name for s in steps] == ["kept"]
            assert (await check.get(AgentRun, run.run_id)).status == AgentRunStatus.SUCCEEDED  # type: ignore[union-attr]
            gone = await check.scalar(
                select(func.count()).select_from(Tenant).where(Tenant.name == "should be rolled back")
            )
            assert gone == 0
    finally:
        tracing.use_session_factory(None)
        async with factory() as s:
            await s.execute(delete(Tenant).where(Tenant.id == t.id))
            await s.commit()
