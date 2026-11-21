"""The only way agent code calls an LLM (CONTRACTS section 6, CLAUDE.md "LLM rules").

    profile = await llm_structured(run, name="icp_builder.profile", tier=ModelTier.SMART, effort="medium",
                                   system=SYSTEM, cached_context=knowledge, user=question,
                                   output_model=CompanyProfile)

The wrapper owns: model routing (tier → LLM_MODEL_SMART / LLM_MODEL_FAST), structured output with Pydantic
validation (one retry on invalid JSON), the tool loop, finish-reason checks (LLMRefused / LLMOutputTruncated),
retries with backoff on 429/5xx/connection errors, a concurrency cap (LLM_MAX_CONCURRENCY), and tracing (one
LLM_CALL step per model call, one TOOL_CALL step per tool call).

`name` is "<agent module>.<call>", e.g. "icp_builder.profile". The part before the first dot is used to
find the agent's PROMPT_VERSION (app.agents.<module>.PROMPT_VERSION) for the trace, and the whole name
selects the mock fixture backend/tests/fixtures/llm/<name>.json.

With USE_MOCK_LLM=true no provider is called: llm_structured returns the fixture if it exists, else a
deterministic polyfactory instance seeded by `name`; llm_tool_loop returns a fixed answer with no tool calls.
"""

import asyncio
import hashlib
import json
import logging
import random
import re
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import BaseModel, ValidationError

from app.adapters.llm import get_llm_provider
from app.adapters.llm.base import Effort, LLMProviderError, LLMResult
from app.agents.pricing import COSTS_ARE_ESTIMATES, cost_usd, price_for
from app.config import settings
from app.core.tracing import RunContext
from app.models.enums import StepType
from app.services.llm_registry import get_active_llm_targets

logger = logging.getLogger("app.llm")

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "llm"
MAX_RETRIES = 4  # retries after the first attempt, for 429 / 5xx / connection errors
MAX_BACKOFF_SECONDS = 30.0
MAX_RETRY_AFTER_SECONDS = 60.0
MOCK_TOOL_LOOP_TEXT = "(mock LLM) This is a placeholder reply."

_sleep = asyncio.sleep  # indirection so tests can skip real waiting


class ModelTier(StrEnum):
    SMART = "smart"  # → settings.LLM_MODEL_SMART: reasoning and writing
    FAST = "fast"  # → settings.LLM_MODEL_FAST: bulk classification and scoring


class LLMRefused(Exception):
    """The model refused, or the provider's content filter blocked the answer."""


class LLMOutputTruncated(Exception):
    """The answer hit max_tokens before it was complete."""


class LLMInvalidOutput(ValueError):
    """The structured answer still failed Pydantic validation after one retry."""


@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[BaseModel], Awaitable[dict[str, Any]]]  # bound server-side to tenant+lead


@dataclass
class ToolLoopResult:
    final_text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    stopped_reason: str = "final_answer"  # final_answer | max_iterations | mock


__all__ = [
    "Effort",
    "LLMInvalidOutput",
    "LLMOutputTruncated",
    "LLMRefused",
    "ModelTier",
    "ToolLoopResult",
    "ToolSpec",
    "llm_structured",
    "llm_tool_loop",
]


# ---------------------------------------------------------------------------------------------- helpers

_semaphores: dict[tuple[int, int], asyncio.Semaphore] = {}


def _semaphore() -> asyncio.Semaphore:
    limit = max(1, settings.LLM_MAX_CONCURRENCY)
    key = (id(asyncio.get_running_loop()), limit)
    if key not in _semaphores:
        _semaphores[key] = asyncio.Semaphore(limit)
    return _semaphores[key]


def _model_for(tier: ModelTier) -> str:
    model = settings.LLM_MODEL_SMART if tier == ModelTier.SMART else settings.LLM_MODEL_FAST
    if not model:
        var = "LLM_MODEL_SMART" if tier == ModelTier.SMART else "LLM_MODEL_FAST"
        raise RuntimeError(f"{var} is not set (see .env.example), or set USE_MOCK_LLM=true.")
    return model


def _prompt_version(name: str) -> str | None:
    module = sys.modules.get(f"app.agents.{name.split('.')[0]}")
    version = getattr(module, "PROMPT_VERSION", None) if module else None
    return str(version) if version else None


def _backoff(attempt: int, retry_after: float | None) -> float:
    delay = min(MAX_BACKOFF_SECONDS, 2.0**attempt) + random.uniform(0, 1)
    if retry_after is not None:
        delay = max(delay, min(retry_after, MAX_RETRY_AFTER_SECONDS))
    return delay


_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def _extract_json(text: str) -> str:
    """Tolerate code fences or prose around the JSON object (small models add them)."""
    stripped = _FENCE_RE.sub("", text.strip())
    start, end = stripped.find("{"), stripped.rfind("}")
    return stripped[start : end + 1] if start != -1 and end > start else stripped


def _validation_feedback(exc: ValidationError) -> str:
    errors = [{"loc": list(e.get("loc", ())), "msg": e.get("msg", "")} for e in exc.errors()]
    return json.dumps(errors, ensure_ascii=False)[:2000]


def _seed(name: str) -> int:
    return int.from_bytes(hashlib.sha256(name.encode("utf-8")).digest()[:8], "big")


def _step_input(
    name: str, tier: ModelTier, effort: Effort, messages: list[dict[str, Any]], **extra: Any
) -> dict:
    return {
        "provider": "mock" if settings.USE_MOCK_LLM else settings.LLM_PROVIDER,
        "prompt": name,
        "prompt_version": _prompt_version(name),
        "tier": tier.value,
        "effort": effort,
        "messages": messages,
        **extra,
    }


async def _complete(
    run: RunContext,
    *,
    name: str,
    tier: ModelTier,
    system: str,
    cached_context: str | None,
    messages: list[dict[str, Any]],
    effort: Effort,
    max_tokens: int,
    lead_id: UUID | None,
    step_input: dict[str, Any],
    json_schema: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> LLMResult:
    """One model call with retries, the concurrency cap, an LLM_CALL step and the finish-reason check."""
    db_targets = await get_active_llm_targets()
    if db_targets:
        candidates: list[tuple[Any, str]] = [
            (t.provider, t.model_smart if tier == ModelTier.SMART else t.model_fast) for t in db_targets
        ]
    else:
        candidates = [(get_llm_provider(), _model_for(tier))]

    last_exc: LLMProviderError | None = None
    for idx, (provider, model) in enumerate(candidates):
        has_fallback = idx + 1 < len(candidates)
        attempt = 0
        while True:
            started = time.perf_counter()
            try:
                async with _semaphore():
                    started = time.perf_counter()
                    result = await provider.complete(
                        model=model,
                        system=system,
                        cached_context=cached_context,
                        messages=messages,
                        effort=effort,
                        max_tokens=max_tokens,
                        json_schema=json_schema,
                        tools=tools,
                    )
                latency_ms = int((time.perf_counter() - started) * 1000)
                last_exc = None
                break
            except LLMProviderError as exc:
                last_exc = exc
                if exc.retryable and attempt < MAX_RETRIES:
                    delay = _backoff(attempt, exc.retry_after)
                    attempt += 1
                    logger.warning("llm %s: %s; retry %d/%d in %.1fs", name, exc, attempt, MAX_RETRIES, delay)
                    await _sleep(delay)
                    continue
                if has_fallback:
                    logger.warning(
                        "llm %s failed on %s (%s); falling back to next provider", name, model, exc
                    )
                    break
                await run.step(
                    StepType.LLM_CALL,
                    name,
                    input={**step_input, "attempts": attempt + 1},
                    output={"error": str(exc), "status_code": exc.status_code},
                    model=model,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    lead_id=lead_id,
                )
                raise
        if last_exc is None:
            break
    if last_exc is not None:
        raise last_exc

    priced_model = model if price_for(model) is not None else result.model
    cost = cost_usd(priced_model, result.usage)
    await run.step(
        StepType.LLM_CALL,
        name,
        input={**step_input, "attempts": attempt + 1},
        output={
            "finish": result.finish,
            "text": result.text,
            "tool_calls": result.tool_calls,
            "cost_estimated": COSTS_ARE_ESTIMATES,
        },
        model=result.model or model,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cache_read_tokens=result.usage.cached_input_tokens,
        cost_usd=cost,
        latency_ms=latency_ms,
        lead_id=lead_id,
    )
    if result.finish == "refused":
        raise LLMRefused(f"{name}: the model refused or the answer was filtered")
    if result.finish == "length":
        raise LLMOutputTruncated(f"{name}: the answer was cut off at max_tokens={max_tokens}")
    return result


# ---------------------------------------------------------------------------------------------- public API


async def llm_structured[T: BaseModel](
    run: RunContext,
    *,
    name: str,
    tier: ModelTier,
    system: str,
    user: str,
    output_model: type[T],
    cached_context: str | None = None,
    effort: Effort = "medium",
    max_tokens: int = 8000,
    lead_id: UUID | None = None,
) -> T:
    """Ask for an answer shaped like `output_model`; returns the validated Pydantic instance."""
    messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
    if settings.USE_MOCK_LLM:
        return await _mock_structured(
            run, name=name, tier=tier, effort=effort, user=user, output_model=output_model, lead_id=lead_id
        )

    schema = output_model.model_json_schema()
    for attempt in (1, 2):
        result = await _complete(
            run,
            name=name,
            tier=tier,
            system=system,
            cached_context=cached_context,
            messages=messages,
            effort=effort,
            max_tokens=max_tokens,
            lead_id=lead_id,
            json_schema=schema,
            step_input=_step_input(
                name,
                tier,
                effort,
                messages[-1:] if attempt == 1 else messages[-2:],
                output_model=output_model.__name__,
                validation_attempt=attempt,
            ),
        )
        try:
            return output_model.model_validate_json(_extract_json(result.text or ""))
        except ValidationError as exc:
            if attempt == 2:
                raise LLMInvalidOutput(
                    f"{name}: the answer did not match {output_model.__name__} after a retry: "
                    f"{_validation_feedback(exc)}"
                ) from exc
            messages = [
                *messages,
                {"role": "assistant", "content": result.text or ""},
                {
                    "role": "user",
                    "content": "Your previous answer did not match the required JSON schema. Errors:\n"
                    f"{_validation_feedback(exc)}\nReply again with only the corrected JSON object.",
                },
            ]
    raise AssertionError("unreachable")  # pragma: no cover


async def llm_tool_loop(
    run: RunContext,
    *,
    name: str,
    tier: ModelTier,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[ToolSpec],
    cached_context: str | None = None,
    effort: Effort = "medium",
    max_iterations: int = 6,
    lead_id: UUID | None = None,
) -> ToolLoopResult:
    """Let the model call `tools` until it gives a final answer or max_iterations model turns have run."""
    if settings.USE_MOCK_LLM:
        return await _mock_tool_loop(
            run, name=name, tier=tier, effort=effort, messages=messages, lead_id=lead_id
        )

    by_name = {tool.name: tool for tool in tools}
    tool_defs = [
        {"name": t.name, "description": t.description, "parameters": t.input_model.model_json_schema()}
        for t in tools
    ]
    convo: list[dict[str, Any]] = list(messages)
    calls: list[dict[str, Any]] = []
    traced_upto = 0
    for iteration in range(1, max_iterations + 1):
        result = await _complete(
            run,
            name=name,
            tier=tier,
            system=system,
            cached_context=cached_context,
            messages=convo,
            effort=effort,
            max_tokens=8000,
            lead_id=lead_id,
            tools=tool_defs,
            step_input=_step_input(name, tier, effort, convo[traced_upto:], iteration=iteration),
        )
        traced_upto = len(convo)
        if not result.tool_calls:
            return ToolLoopResult(result.text or "", calls, iteration, "final_answer")

        convo.append({"role": "assistant", "content": result.text, "tool_calls": result.tool_calls})
        outcomes = await asyncio.gather(
            *(_run_tool(run, name, by_name, call, lead_id) for call in result.tool_calls)
        )
        for call, (content, record) in zip(result.tool_calls, outcomes, strict=True):
            convo.append({"role": "tool", "tool_call_id": call["id"], "content": content})
            calls.append(record)
    return ToolLoopResult("", calls, max_iterations, "max_iterations")


async def _run_tool(
    run: RunContext, loop_name: str, by_name: dict[str, ToolSpec], call: dict[str, Any], lead_id: UUID | None
) -> tuple[str, dict[str, Any]]:
    """Validate the arguments, run the handler, record a TOOL_CALL step. Errors go back as data."""
    tool_name = str(call.get("name", ""))
    arguments = call.get("arguments") or {}
    started = time.perf_counter()
    spec = by_name.get(tool_name)
    payload: dict[str, Any]
    if spec is None:
        payload = {"is_error": True, "error": f"Unknown tool {tool_name!r}."}
    else:
        try:
            parsed = spec.input_model.model_validate(arguments)
        except ValidationError as exc:
            payload = {"is_error": True, "error": f"Invalid arguments: {_validation_feedback(exc)}"}
        else:
            try:
                payload = await spec.handler(parsed)
            except Exception as exc:
                logger.warning("tool %s failed: %s", tool_name, exc)
                payload = {"is_error": True, "error": f"{type(exc).__name__}: {exc}"}
    is_error = bool(payload.get("is_error"))
    await run.step(
        StepType.TOOL_CALL,
        f"{loop_name}.{tool_name}",
        input=arguments,
        output=payload,
        latency_ms=int((time.perf_counter() - started) * 1000),
        lead_id=lead_id,
    )
    record = {
        "id": call.get("id"),
        "name": tool_name,
        "arguments": arguments,
        "result": payload,
        "is_error": is_error,
    }
    return json.dumps(payload, ensure_ascii=False, default=str), record


# ---------------------------------------------------------------------------------------------- mock mode


async def _mock_structured[T: BaseModel](
    run: RunContext,
    *,
    name: str,
    tier: ModelTier,
    effort: Effort,
    user: str,
    output_model: type[T],
    lead_id: UUID | None,
) -> T:
    fixture = FIXTURES_DIR / f"{name}.json"
    if fixture.is_file():
        result = output_model.model_validate_json(fixture.read_text(encoding="utf-8"))
        source = f"fixture:{fixture.name}"
    else:
        factory = ModelFactory.create_factory(output_model)
        factory.seed_random(_seed(name))
        result = factory.build()
        source = "polyfactory"
    await run.step(
        StepType.LLM_CALL,
        name,
        input=_step_input(
            name,
            tier,
            effort,
            [{"role": "user", "content": user}],
            output_model=output_model.__name__,
            mock_source=source,
        ),
        output=result,
        model="mock",
        lead_id=lead_id,
    )
    return result


async def _mock_tool_loop(
    run: RunContext,
    *,
    name: str,
    tier: ModelTier,
    effort: Effort,
    messages: list[dict[str, Any]],
    lead_id: UUID | None,
) -> ToolLoopResult:
    await run.step(
        StepType.LLM_CALL,
        name,
        input=_step_input(name, tier, effort, messages[-1:]),
        output={"finish": "stop", "text": MOCK_TOOL_LOOP_TEXT, "tool_calls": []},
        model="mock",
        lead_id=lead_id,
    )
    return ToolLoopResult(MOCK_TOOL_LOOP_TEXT, [], 1, "mock")
