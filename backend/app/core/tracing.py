"""Agent run tracing (CONTRACTS section 5). If it isn't traced, it didn't happen.

Every agent job runs inside `agent_run(...)`, which creates (or reuses) an `agent_runs` row and yields a
`RunContext`. Each step (`ctx.step(...)`) is written to `agent_steps` immediately, in its own short DB
session and transaction, so the trace survives even when the job's main transaction rolls back.

    async with agent_run(tenant_id, AgentRunKind.SCORING, trigger="chained", input={"lead_ids": ids}) as run:
        result = await llm_structured(run, name="lead_scorer.batch", ...)   # records an LLM_CALL step
        await run.step(StepType.DECISION, "threshold", output={"qualified": 12})
        run.output_summary = {"qualified": 12}

On exit the run is marked succeeded (or failed, with the error text and an ERROR step, and the exception is
re-raised) and its token and cost totals are aggregated.

Payloads are made JSON-safe, phone numbers are masked (last 3 digits kept), and each field is capped at 20 KB.
"""

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic_core import to_jsonable_python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AgentRunKind, AgentRunStatus, StepType
from app.models.runs import AgentRun, AgentStep

logger = logging.getLogger("app.tracing")

MAX_FIELD_BYTES = 20 * 1024
MAX_ERROR_CHARS = 4000

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
_session_factory: SessionFactory | None = None


def use_session_factory(factory: SessionFactory | None) -> None:
    """Point trace writes at another session factory (tests); None restores app.db.SessionLocal."""
    global _session_factory
    _session_factory = factory


def _trace_session() -> AbstractAsyncContextManager[AsyncSession]:
    if _session_factory is not None:
        return _session_factory()
    from app.db import SessionLocal

    return SessionLocal()


# ---------------------------------------------------------------------------------------------- payload safet

# A phone-like run of 10-15 digits (optionally +, spaces allowed between digits), not part of a longer token.
# Dashes are not allowed inside, so dates ("2026-11-18") and UUIDs are left alone.
_PHONE_RE = re.compile(r"(?<![\w+-])\+?\d(?: ?\d){9,14}(?![\w-])")


def _mask_phone(match: re.Match[str]) -> str:
    raw = match.group(0)
    total_digits = sum(ch.isdigit() for ch in raw)
    out: list[str] = []
    seen = 0
    for ch in raw:
        if ch.isdigit():
            seen += 1
            out.append(ch if seen > total_digits - 3 else "*")
        else:
            out.append(ch)
    return "".join(out)


def mask_phones(text: str) -> str:
    """Mask phone numbers in free text, keeping the last 3 digits: +201012345678 → +*********678."""
    return _PHONE_RE.sub(_mask_phone, text)


def _mask_value(value: Any) -> Any:
    if isinstance(value, str):
        return mask_phones(value)
    if isinstance(value, dict):
        return {str(k): _mask_value(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_mask_value(v) for v in value]
    return value


def _to_jsonable(value: Any) -> Any:
    """Pydantic models (also nested), UUIDs, datetimes, Decimals → plain JSON values; anything else → str."""
    return to_jsonable_python(value, fallback=str)


def safe_payload(value: Any) -> Any:
    """JSON-safe, phone-masked, size-capped version of `value` for a jsonb trace column."""
    if value is None:
        return None
    data = _mask_value(_to_jsonable(value))
    encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
    if len(encoded) <= MAX_FIELD_BYTES:
        return data
    preview = encoded[: MAX_FIELD_BYTES - 200].decode("utf-8", errors="ignore")
    return {"_truncated": True, "_original_bytes": len(encoded), "preview": preview}


def _error_text(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    return mask_phones(text)[:MAX_ERROR_CHARS]


# ---------------------------------------------------------------------------------------------- run context


class RunContext:
    """One agent run. Pass it to llm_structured / llm_tool_loop; record your own steps with step()."""

    def __init__(self, run_id: uuid.UUID, tenant_id: uuid.UUID, kind: AgentRunKind) -> None:
        self.run_id = run_id
        self.tenant_id = tenant_id
        self.kind = kind
        self.output_summary: dict[str, Any] | None = None  # set by the job; stored on the run at exit
        self._seq = 0
        self._lock = asyncio.Lock()  # keeps seq ordered and trace writes serial (parallel tool calls)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0

    async def step(
        self,
        step_type: StepType,
        name: str,
        *,
        input: Any = None,
        output: Any = None,
        model: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cost_usd: float = 0.0,
        latency_ms: int = 0,
        lead_id: uuid.UUID | None = None,
    ) -> None:
        async with self._lock:
            self._seq += 1
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cost_usd += cost_usd
            row = AgentStep(
                created_at=_now(),
                tenant_id=self.tenant_id,
                run_id=self.run_id,
                seq=self._seq,
                step_type=StepType(step_type).value,
                name=name,
                input=safe_payload(input),
                output=safe_payload(output),
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read_tokens,
                cost_usd=Decimal(str(round(cost_usd, 6))),
                latency_ms=latency_ms,
                lead_id=lead_id,
            )
            async with _trace_session() as session:
                session.add(row)
                await session.commit()


def _now() -> datetime:
    return datetime.now(UTC)


async def create_queued_run(
    session: AsyncSession, tenant_id: uuid.UUID, kind: AgentRunKind, *, trigger: str, input: dict[str, Any]
) -> uuid.UUID:
    """Pre-create a run with status=queued in the caller's session (an API endpoint, before enqueueing).

    The caller commits. The job then passes the id to agent_run(..., run_id=...), which reuses the row.
    """
    run = AgentRun(
        id=uuid.uuid4(),
        created_at=_now(),
        tenant_id=tenant_id,
        kind=AgentRunKind(kind).value,
        status=AgentRunStatus.QUEUED.value,
        trigger=trigger,
        input=safe_payload(input) or {},
    )
    session.add(run)
    await session.flush()
    return run.id


@asynccontextmanager
async def agent_run(
    tenant_id: uuid.UUID,
    kind: AgentRunKind,
    *,
    trigger: str,
    input: dict[str, Any],
    run_id: uuid.UUID | None = None,
) -> AsyncIterator[RunContext]:
    """Open (or reuse) an agent run, yield its RunContext, and close it as succeeded or failed."""
    async with _trace_session() as session:
        run: AgentRun | None = None
        if run_id is not None:
            run = (
                await session.execute(
                    select(AgentRun).where(AgentRun.id == run_id, AgentRun.tenant_id == tenant_id)
                )
            ).scalar_one_or_none()
        if run is None:
            run = AgentRun(
                id=run_id or uuid.uuid4(),
                created_at=_now(),
                tenant_id=tenant_id,
                kind=AgentRunKind(kind).value,
                trigger=trigger,
                input=safe_payload(input) or {},
            )
            session.add(run)
        run.status = AgentRunStatus.RUNNING.value
        run.started_at = _now()
        await session.commit()
        ctx = RunContext(run.id, tenant_id, AgentRunKind(kind))

    status = AgentRunStatus.SUCCEEDED
    error: str | None = None
    try:
        yield ctx
    except BaseException as exc:
        cancelled = isinstance(exc, asyncio.CancelledError)
        status = AgentRunStatus.CANCELLED if cancelled else AgentRunStatus.FAILED
        error = _error_text(exc)
        try:
            await ctx.step(StepType.ERROR, type(exc).__name__, output={"error": error})
        except Exception:  # never hide the original error behind a trace failure
            logger.exception("tracing: could not record the error step for run %s", ctx.run_id)
        raise
    finally:
        try:
            await _finish(ctx, status, error)
        except Exception:
            logger.exception("tracing: could not close run %s", ctx.run_id)


async def _finish(ctx: RunContext, status: AgentRunStatus, error: str | None) -> None:
    async with _trace_session() as session:
        run = await session.get(AgentRun, ctx.run_id)
        if run is None:
            return
        run.status = status.value
        run.error = error
        run.finished_at = _now()
        run.total_input_tokens = ctx.total_input_tokens
        run.total_output_tokens = ctx.total_output_tokens
        run.total_cost_usd = Decimal(str(round(ctx.total_cost_usd, 6)))
        if ctx.output_summary is not None:
            run.output_summary = safe_payload(ctx.output_summary)
        await session.commit()
