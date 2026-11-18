"""app.agents.llm with a scripted fake provider (real mode) and in mock mode."""

import asyncio
import sys
import types
from collections.abc import AsyncIterator
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm.base import LLMProviderError, LLMResult, LLMUsage
from app.agents import llm, pricing
from app.agents.llm import (
    LLMInvalidOutput,
    LLMOutputTruncated,
    LLMRefused,
    ModelTier,
    ToolSpec,
    llm_structured,
    llm_tool_loop,
)
from app.agents.pricing import ModelPrice
from app.config import settings
from app.core.tracing import RunContext, agent_run
from app.models.enums import AgentRunKind
from app.models.runs import AgentStep
from app.models.tenants import Tenant


class Score(BaseModel):
    score: int
    reasons: list[str]


def ok(text: str | None = '{"score": 7, "reasons": ["near"]}', **kw: Any) -> LLMResult:
    return LLMResult(
        text=text,
        tool_calls=kw.get("tool_calls", []),
        finish=kw.get("finish", "stop"),
        usage=LLMUsage(input_tokens=1000, output_tokens=100, cached_input_tokens=800),
        model=kw.get("model", "fast-m"),
        raw={},
    )


class FakeProvider:
    name = "fake"

    def __init__(self, script: list[LLMResult | Exception], delay: float = 0.0) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []
        self.delay = delay
        self.active = 0
        self.max_active = 0

    async def complete(self, **kwargs: Any) -> LLMResult:
        self.calls.append(kwargs)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
            if isinstance(item, Exception):
                raise item
            return item
        finally:
            self.active -= 1


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []

    async def fake_sleep(delay: float) -> None:
        recorded.append(delay)

    monkeypatch.setattr(llm, "_sleep", fake_sleep)
    return recorded


@pytest.fixture
def real_mode(monkeypatch: pytest.MonkeyPatch, sleeps: list[float]) -> None:
    monkeypatch.setattr(settings, "USE_MOCK_LLM", False)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai_compatible")
    monkeypatch.setattr(settings, "LLM_MODEL_SMART", "smart-m")
    monkeypatch.setattr(settings, "LLM_MODEL_FAST", "fast-m")
    monkeypatch.setattr(settings, "LLM_MAX_CONCURRENCY", 2)
    monkeypatch.setitem(pricing.PRICES, "fast-m", ModelPrice(input=1.0, output=4.0, cached_input=0.25))
    agent_module = types.ModuleType("app.agents.demo_agent")
    agent_module.PROMPT_VERSION = "demo_agent@3"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "app.agents.demo_agent", agent_module)


def use(monkeypatch: pytest.MonkeyPatch, fake: FakeProvider) -> FakeProvider:
    monkeypatch.setattr(llm, "get_llm_provider", lambda: fake)
    return fake


@pytest.fixture
async def run(session: AsyncSession) -> AsyncIterator[RunContext]:
    tenant = Tenant(name="LLM test")
    session.add(tenant)
    await session.flush()
    async with agent_run(tenant.id, AgentRunKind.SCORING, trigger="manual", input={}) as ctx:
        yield ctx


async def steps(session: AsyncSession, run: RunContext) -> list[AgentStep]:
    stmt = select(AgentStep).where(AgentStep.run_id == run.run_id).order_by(AgentStep.seq)
    return list((await session.execute(stmt.execution_options(populate_existing=True))).scalars())


async def structured(run: RunContext, **kw: Any) -> Score:
    args: dict[str, Any] = {
        "name": "demo_agent.score",
        "tier": ModelTier.FAST,
        "system": "Score the lead.",
        "user": "<lead>Shop</lead>",
        "output_model": Score,
        "cached_context": "ICP: kids wear",
        "effort": "low",
    }
    args.update(kw)
    return await llm_structured(run, **args)


# ---------------------------------------------------------------------------------------------- structured


@pytest.mark.usefixtures("real_mode")
async def test_valid_output_is_parsed_and_traced(
    monkeypatch: pytest.MonkeyPatch, run: RunContext, session: AsyncSession
) -> None:
    fake = use(monkeypatch, FakeProvider([ok()]))
    result = await structured(run)
    assert result == Score(score=7, reasons=["near"])

    sent = fake.calls[0]
    assert sent["model"] == "fast-m"
    assert sent["effort"] == "low"
    assert sent["system"] == "Score the lead."
    assert sent["cached_context"] == "ICP: kids wear"  # the stable part is separate and first
    assert sent["messages"] == [{"role": "user", "content": "<lead>Shop</lead>"}]
    assert sent["json_schema"] == Score.model_json_schema()

    (step,) = await steps(session, run)
    assert step.step_type == "llm_call" and step.name == "demo_agent.score"
    assert step.model == "fast-m"
    assert (step.input_tokens, step.output_tokens, step.cache_read_tokens) == (1000, 100, 800)
    # 200 uncached * $1 + 800 cached * $0.25 + 100 output * $4, per 1M tokens
    assert float(step.cost_usd) == pytest.approx(0.0008)
    assert step.input["prompt_version"] == "demo_agent@3"
    assert step.input["provider"] == "openai_compatible"
    assert step.output["cost_estimated"] is True


@pytest.mark.usefixtures("real_mode")
async def test_smart_tier_routes_to_the_smart_model(monkeypatch: pytest.MonkeyPatch, run: RunContext) -> None:
    fake = use(monkeypatch, FakeProvider([ok()]))
    await structured(run, tier=ModelTier.SMART, effort="medium")
    assert fake.calls[0]["model"] == "smart-m"
    assert fake.calls[0]["effort"] == "medium"


@pytest.mark.usefixtures("real_mode")
async def test_code_fences_around_json_are_tolerated(
    monkeypatch: pytest.MonkeyPatch, run: RunContext
) -> None:
    use(monkeypatch, FakeProvider([ok('```json\n{"score": 2, "reasons": []}\n```')]))
    assert (await structured(run)).score == 2


@pytest.mark.usefixtures("real_mode")
async def test_invalid_json_is_retried_once_with_the_errors(
    monkeypatch: pytest.MonkeyPatch, run: RunContext, session: AsyncSession
) -> None:
    fake = use(monkeypatch, FakeProvider([ok('{"score": "high"}'), ok('{"score": 5, "reasons": ["ok"]}')]))
    assert (await structured(run)).score == 5
    retry_messages = fake.calls[1]["messages"]
    assert retry_messages[0] == {"role": "user", "content": "<lead>Shop</lead>"}
    assert retry_messages[1] == {"role": "assistant", "content": '{"score": "high"}'}
    assert "did not match" in retry_messages[2]["content"]
    assert fake.calls[1]["cached_context"] == "ICP: kids wear"
    assert len(await steps(session, run)) == 2


@pytest.mark.usefixtures("real_mode")
async def test_invalid_json_twice_raises(monkeypatch: pytest.MonkeyPatch, run: RunContext) -> None:
    fake = use(monkeypatch, FakeProvider([ok("not json"), ok('{"score": null}')]))
    with pytest.raises(LLMInvalidOutput, match="Score"):
        await structured(run)
    assert len(fake.calls) == 2


@pytest.mark.usefixtures("real_mode")
async def test_refusal_raises_and_is_recorded(
    monkeypatch: pytest.MonkeyPatch, run: RunContext, session: AsyncSession
) -> None:
    use(monkeypatch, FakeProvider([ok(None, finish="refused")]))
    with pytest.raises(LLMRefused):
        await structured(run)
    (step,) = await steps(session, run)
    assert step.output["finish"] == "refused"


@pytest.mark.usefixtures("real_mode")
async def test_truncated_output_raises(monkeypatch: pytest.MonkeyPatch, run: RunContext) -> None:
    use(monkeypatch, FakeProvider([ok('{"score": 1', finish="length")]))
    with pytest.raises(LLMOutputTruncated):
        await structured(run)


@pytest.mark.usefixtures("real_mode")
async def test_429_and_503_are_retried_with_backoff(
    monkeypatch: pytest.MonkeyPatch, run: RunContext, sleeps: list[float], session: AsyncSession
) -> None:
    fake = use(
        monkeypatch,
        FakeProvider(
            [
                LLMProviderError("rate limited", retryable=True, status_code=429, retry_after=7),
                LLMProviderError("unavailable", retryable=True, status_code=503),
                ok(),
            ]
        ),
    )
    assert (await structured(run)).score == 7
    assert len(fake.calls) == 3
    assert sleeps[0] >= 7  # Retry-After respected
    assert 2 <= sleeps[1] < 3  # 2^1 + jitter
    (step,) = await steps(session, run)
    assert step.input["attempts"] == 3


@pytest.mark.usefixtures("real_mode")
async def test_400_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, run: RunContext, sleeps: list[float], session: AsyncSession
) -> None:
    fake = use(monkeypatch, FakeProvider([LLMProviderError("bad request", retryable=False, status_code=400)]))
    with pytest.raises(LLMProviderError):
        await structured(run)
    assert len(fake.calls) == 1
    assert sleeps == []
    (step,) = await steps(session, run)
    assert step.output["status_code"] == 400


@pytest.mark.usefixtures("real_mode")
async def test_gives_up_after_max_retries(monkeypatch: pytest.MonkeyPatch, run: RunContext) -> None:
    fake = use(monkeypatch, FakeProvider([LLMProviderError("down", retryable=True, status_code=500)]))
    with pytest.raises(LLMProviderError):
        await structured(run)
    assert len(fake.calls) == llm.MAX_RETRIES + 1


@pytest.mark.usefixtures("real_mode")
async def test_concurrency_is_capped(monkeypatch: pytest.MonkeyPatch, run: RunContext) -> None:
    fake = use(monkeypatch, FakeProvider([ok()], delay=0.02))
    results = await asyncio.gather(*(structured(run) for _ in range(10)))
    assert len(results) == 10
    assert fake.max_active == 2


# ---------------------------------------------------------------------------------------------- tool loop


class Query(BaseModel):
    query: str


class Status(BaseModel):
    status: str


def tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"id": call_id, "name": name, "arguments": arguments}


@pytest.mark.usefixtures("real_mode")
async def test_tool_loop_runs_two_tool_calls_in_parallel(
    monkeypatch: pytest.MonkeyPatch, run: RunContext, session: AsyncSession
) -> None:
    started_a, started_b = asyncio.Event(), asyncio.Event()

    async def search(args: BaseModel) -> dict[str, Any]:
        started_a.set()
        await asyncio.wait_for(started_b.wait(), 1)  # deadlocks (times out) if tools ran one by one
        return {"results": [f"found {args.query}"]}  # type: ignore[attr-defined]

    async def set_status(args: BaseModel) -> dict[str, Any]:
        started_b.set()
        await asyncio.wait_for(started_a.wait(), 1)
        return {"ok": True, "status": args.status}  # type: ignore[attr-defined]

    tools = [
        ToolSpec("search_knowledge", "Search the company files", Query, search),
        ToolSpec("set_lead_status", "Set the lead status", Status, set_status),
    ]
    fake = use(
        monkeypatch,
        FakeProvider(
            [
                ok(
                    None,
                    finish="tool_calls",
                    tool_calls=[
                        tool_call("c1", "search_knowledge", {"query": "prices"}),
                        tool_call("c2", "set_lead_status", {"status": "interested"}),
                    ],
                ),
                ok("أهلاً! الأسعار في الكتالوج."),
            ]
        ),
    )
    result = await llm_tool_loop(
        run,
        name="demo_agent.reply",
        tier=ModelTier.SMART,
        system="You reply to leads.",
        messages=[{"role": "user", "content": "<lead_message>بكام؟</lead_message>"}],
        tools=tools,
        effort="medium",
    )
    assert result.final_text == "أهلاً! الأسعار في الكتالوج."
    assert result.iterations == 2 and result.stopped_reason == "final_answer"
    assert [c["name"] for c in result.tool_calls] == ["search_knowledge", "set_lead_status"]
    assert not any(c["is_error"] for c in result.tool_calls)

    second = fake.calls[1]["messages"]
    assert second[1]["role"] == "assistant" and len(second[1]["tool_calls"]) == 2
    assert second[2] == {"role": "tool", "tool_call_id": "c1", "content": '{"results": ["found prices"]}'}
    assert second[3]["tool_call_id"] == "c2"
    assert fake.calls[0]["tools"][0]["parameters"] == Query.model_json_schema()

    recorded = await steps(session, run)
    assert [s.step_type for s in recorded] == ["llm_call", "tool_call", "tool_call", "llm_call"]
    assert {s.name for s in recorded if s.step_type == "tool_call"} == {
        "demo_agent.reply.search_knowledge",
        "demo_agent.reply.set_lead_status",
    }


@pytest.mark.usefixtures("real_mode")
async def test_tool_errors_go_back_to_the_model(monkeypatch: pytest.MonkeyPatch, run: RunContext) -> None:
    handled: list[str] = []

    async def search(args: BaseModel) -> dict[str, Any]:
        handled.append("search")
        return {}

    async def broken(args: BaseModel) -> dict[str, Any]:
        raise RuntimeError("db down")

    tools = [ToolSpec("search_knowledge", "", Query, search), ToolSpec("set_lead_status", "", Status, broken)]
    fake = use(
        monkeypatch,
        FakeProvider(
            [
                ok(
                    None,
                    finish="tool_calls",
                    tool_calls=[
                        tool_call("c1", "search_knowledge", {"wrong": 1}),
                        tool_call("c2", "set_lead_status", {"status": "x"}),
                        tool_call("c3", "give_discount", {"percent": 50}),
                    ],
                ),
                ok("done"),
            ]
        ),
    )
    result = await llm_tool_loop(
        run, name="demo_agent.reply", tier=ModelTier.SMART, system="s", messages=[], tools=tools, effort="low"
    )
    assert handled == []  # invalid input never reaches the handler
    assert [c["is_error"] for c in result.tool_calls] == [True, True, True]
    contents = [m["content"] for m in fake.calls[1]["messages"] if m["role"] == "tool"]
    assert "Invalid arguments" in contents[0]
    assert "RuntimeError: db down" in contents[1]
    assert "Unknown tool 'give_discount'" in contents[2]


@pytest.mark.usefixtures("real_mode")
async def test_tool_loop_stops_at_max_iterations(monkeypatch: pytest.MonkeyPatch, run: RunContext) -> None:
    async def search(args: BaseModel) -> dict[str, Any]:
        return {"results": []}

    looping = ok(None, finish="tool_calls", tool_calls=[tool_call("c", "search_knowledge", {"query": "q"})])
    fake = use(monkeypatch, FakeProvider([looping]))
    result = await llm_tool_loop(
        run,
        name="demo_agent.reply",
        tier=ModelTier.SMART,
        system="s",
        messages=[],
        tools=[ToolSpec("search_knowledge", "", Query, search)],
        effort="low",
        max_iterations=3,
    )
    assert result.stopped_reason == "max_iterations"
    assert result.iterations == 3
    assert len(fake.calls) == 3


# ---------------------------------------------------------------------------------------------- mock mode


def no_provider() -> None:
    raise AssertionError("mock mode must not call a provider")


async def test_mock_mode_uses_the_fixture_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, run: RunContext, session: AsyncSession
) -> None:
    monkeypatch.setattr(llm, "get_llm_provider", no_provider)
    monkeypatch.setattr(llm, "FIXTURES_DIR", tmp_path)
    (tmp_path / "demo_agent.score.json").write_text('{"score": 9, "reasons": ["قريب"]}', encoding="utf-8")

    assert await structured(run) == Score(score=9, reasons=["قريب"])
    (step,) = await steps(session, run)
    assert step.model == "mock"
    assert float(step.cost_usd) == 0
    assert step.input["mock_source"] == "fixture:demo_agent.score.json"


async def test_mock_mode_without_fixture_is_deterministic_by_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, run: RunContext
) -> None:
    monkeypatch.setattr(llm, "get_llm_provider", no_provider)
    monkeypatch.setattr(llm, "FIXTURES_DIR", tmp_path)
    a1 = await structured(run, name="demo_agent.a")
    a2 = await structured(run, name="demo_agent.a")
    b = await structured(run, name="demo_agent.b")
    assert isinstance(a1, Score)
    assert a1 == a2
    assert a1 != b


async def test_mock_tool_loop_returns_a_fixed_answer(
    monkeypatch: pytest.MonkeyPatch, run: RunContext, session: AsyncSession
) -> None:
    monkeypatch.setattr(llm, "get_llm_provider", no_provider)
    result = await llm_tool_loop(
        run, name="demo_agent.reply", tier=ModelTier.SMART, system="s", messages=[], tools=[], effort="low"
    )
    assert result.tool_calls == [] and result.final_text
    (step,) = await steps(session, run)
    assert step.model == "mock"


def test_pricing_bills_cached_tokens_at_the_cached_price(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(pricing.PRICES, "m", ModelPrice(input=2.0, output=8.0, cached_input=0.5))
    usage = LLMUsage(input_tokens=1_000_000, output_tokens=500_000, cached_input_tokens=400_000)
    assert pricing.cost_usd("m", usage) == pytest.approx(0.6 * 2 + 0.4 * 0.5 + 0.5 * 8)
    assert pricing.cost_usd("unknown-model", usage) == 0.0
