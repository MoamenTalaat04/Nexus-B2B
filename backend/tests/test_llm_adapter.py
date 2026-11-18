"""The openai_compatible provider with the HTTP layer mocked (no real API calls).

The openai SDK sends requests through `httpx2`, which respx does not patch, so these tests inject an
`httpx2.AsyncClient` with a `MockTransport`: the SDK builds and parses real HTTP requests and responses,
and only the network is replaced.
"""

import json
from typing import Any

import httpx2
import pytest

from app.adapters import llm as llm_adapters
from app.adapters.llm import LLMConfigError, LLMProviderError, get_llm_provider
from app.adapters.llm.openai_compatible import OpenAICompatibleProvider
from app.config import settings

BASE = "https://llm.test/v1"
SCHEMA = {
    "title": "Score",
    "type": "object",
    "properties": {"score": {"type": "integer"}},
    "required": ["score"],
}


class MockHTTP:
    """Scripted responses for POST {BASE}/chat/completions; records every request. The last item repeats."""

    def __init__(
        self, *script: dict[str, Any] | tuple[int, dict[str, Any], dict[str, str]] | Exception
    ) -> None:
        self.script = list(script)
        self.requests: list[httpx2.Request] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert str(request.url) == f"{BASE}/chat/completions"
        self.requests.append(request)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            status, payload, headers = item
            return httpx2.Response(status, json=payload, headers=headers)
        return httpx2.Response(200, json=item)

    def body(self, index: int = -1) -> dict[str, Any]:
        return json.loads(self.requests[index].content)


def completion(
    *,
    content: str | None = "ok",
    finish: str = "stop",
    tool_calls: list[dict[str, Any]] | None = None,
    refusal: str | None = None,
    prompt_tokens: int = 100,
    completion_tokens: int = 20,
    cached: int | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    if refusal:
        message["refusal"] = refusal
    usage: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    if cached is not None:
        usage["prompt_tokens_details"] = {"cached_tokens": cached}
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "fast-model",
        "choices": [{"index": 0, "finish_reason": finish, "message": message}],
        "usage": usage,
    }


def error(status: int, retry_after: str | None = "7") -> tuple[int, dict[str, Any], dict[str, str]]:
    headers = {"retry-after": retry_after} if retry_after else {}
    return status, {"error": {"message": "nope"}}, headers


def provider(http: MockHTTP, reasoning: set[str] | None = None) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url=BASE,
        api_key="test-key",
        timeout=5,
        reasoning_models=reasoning or set(),
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(http.handle)),
    )


async def call(p: OpenAICompatibleProvider, **overrides: Any) -> Any:
    args: dict[str, Any] = {
        "model": "fast-model",
        "system": "You score leads.",
        "cached_context": "<company_files>stable</company_files>",
        "messages": [{"role": "user", "content": "lead 1"}],
        "effort": "low",
        "max_tokens": 500,
    }
    args.update(overrides)
    return await p.complete(**args)


async def test_json_schema_request_puts_the_stable_part_first() -> None:
    http = MockHTTP(completion(content='{"score": 7}'))
    result = await call(provider(http), json_schema=SCHEMA)

    sent = http.body()
    assert sent["model"] == "fast-model"
    assert sent["messages"][0] == {
        "role": "system",
        "content": "You score leads.\n\n<company_files>stable</company_files>",
    }
    assert sent["messages"][1] == {"role": "user", "content": "lead 1"}
    assert sent["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "Score", "schema": SCHEMA, "strict": True},
    }
    assert sent["max_tokens"] == 500
    assert "reasoning_effort" not in sent
    assert "tools" not in sent
    assert http.requests[0].headers["authorization"] == "Bearer test-key"
    assert result.text == '{"score": 7}' and result.finish == "stop"


async def test_reasoning_effort_is_sent_only_to_listed_models() -> None:
    http = MockHTTP(completion())
    await call(provider(http, {"fast-model"}), effort="medium")
    sent = http.body()
    assert sent["reasoning_effort"] == "medium"
    assert sent["max_completion_tokens"] == 500
    assert "max_tokens" not in sent


async def test_strict_schema_rejection_falls_back_to_json_object() -> None:
    http = MockHTTP(
        error(400, retry_after=None),
        completion(content='{"score": 3}'),
        completion(content='{"score": 4}'),
    )
    p = provider(http)
    result = await call(p, json_schema=SCHEMA)
    assert result.text == '{"score": 3}'
    fallback = http.body(1)
    assert fallback["response_format"] == {"type": "json_object"}
    assert "JSON schema" in fallback["messages"][0]["content"]
    assert '"score"' in fallback["messages"][0]["content"]

    await call(p, json_schema=SCHEMA)  # the model is remembered: no strict attempt again
    assert len(http.requests) == 3
    assert http.body(2)["response_format"] == {"type": "json_object"}


async def test_tools_and_tool_call_parsing() -> None:
    tool_calls = [
        {
            "id": "c1",
            "type": "function",
            "function": {"name": "search_knowledge", "arguments": '{"query": "سعر"}'},
        },
        {"id": "c2", "type": "function", "function": {"name": "set_lead_status", "arguments": "not json"}},
    ]
    http = MockHTTP(completion(content=None, finish="tool_calls", tool_calls=tool_calls))
    tools = [{"name": "search_knowledge", "description": "Search files", "parameters": {"type": "object"}}]
    history = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "c0", "name": "x", "arguments": {"a": 1}}],
        },
        {"role": "tool", "tool_call_id": "c0", "content": '{"ok": true}'},
    ]
    result = await call(provider(http), messages=history, tools=tools)

    sent = http.body()
    assert sent["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "search_knowledge",
                "description": "Search files",
                "parameters": {"type": "object"},
            },
        }
    ]
    assert sent["tool_choice"] == "auto"
    assert sent["messages"][2]["tool_calls"] == [
        {"id": "c0", "type": "function", "function": {"name": "x", "arguments": '{"a": 1}'}}
    ]
    assert sent["messages"][3] == {"role": "tool", "tool_call_id": "c0", "content": '{"ok": true}'}
    assert result.finish == "tool_calls"
    assert result.text is None
    assert result.tool_calls == [
        {"id": "c1", "name": "search_knowledge", "arguments": {"query": "سعر"}},
        {"id": "c2", "name": "set_lead_status", "arguments": {"_invalid_json": "not json"}},
    ]


@pytest.mark.parametrize(
    ("finish", "refusal", "expected"),
    [
        ("stop", None, "stop"),
        ("length", None, "length"),
        ("content_filter", None, "refused"),
        ("stop", "I can't help with that.", "refused"),
    ],
)
async def test_finish_reason_mapping(finish: str, refusal: str | None, expected: str) -> None:
    http = MockHTTP(completion(finish=finish, refusal=refusal))
    assert (await call(provider(http))).finish == expected


async def test_usage_mapping_includes_cached_tokens() -> None:
    http = MockHTTP(completion(prompt_tokens=1200, completion_tokens=80, cached=1000))
    result = await call(provider(http))
    assert result.usage.model_dump() == {
        "input_tokens": 1200,
        "output_tokens": 80,
        "cached_input_tokens": 1000,
    }
    assert result.model == "fast-model"
    assert result.raw["id"] == "chatcmpl-1"

    assert (await call(provider(MockHTTP(completion())))).usage.cached_input_tokens == 0


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(429, True), (500, True), (503, True), (400, False), (401, False), (404, False)],
)
async def test_error_mapping(status: int, retryable: bool) -> None:
    http = MockHTTP(error(status))
    with pytest.raises(LLMProviderError) as info:
        await call(provider(http))
    assert info.value.retryable is retryable
    assert info.value.status_code == status
    assert info.value.retry_after == (7.0 if retryable else None)
    assert len(http.requests) == 1  # the SDK's own retries are off


async def test_connection_errors_are_retryable() -> None:
    http = MockHTTP(httpx2.ConnectError("down"))
    with pytest.raises(LLMProviderError) as info:
        await call(provider(http))
    assert info.value.retryable is True
    assert info.value.status_code is None


def test_get_llm_provider_validates_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    llm_adapters._cache.clear()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "nope")
    with pytest.raises(LLMConfigError, match="Unknown LLM_PROVIDER"):
        get_llm_provider()

    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai_compatible")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    monkeypatch.setattr(settings, "LLM_API_KEY", "k")
    with pytest.raises(LLMConfigError, match="LLM_BASE_URL"):
        get_llm_provider()

    monkeypatch.setattr(settings, "LLM_BASE_URL", BASE)
    first = get_llm_provider()
    assert isinstance(first, OpenAICompatibleProvider)
    assert get_llm_provider() is first
    llm_adapters._cache.clear()


async def test_gemini_thought_signature_is_sent_back_unchanged() -> None:
    """Gemini 3+ rejects a follow-up turn (HTTP 400) unless the tool call's thought signature comes back."""
    signed = {
        "id": "c1",
        "type": "function",
        "function": {"name": "lookup_price", "arguments": '{"product": "tshirt"}'},
        "extra_content": {"google": {"thought_signature": "SIG-abc123"}},
    }
    plain = {"id": "c2", "type": "function", "function": {"name": "lookup_price", "arguments": "{}"}}
    http = MockHTTP(completion(content=None, finish="tool_calls", tool_calls=[signed, plain]), completion())
    p = provider(http)
    first = await call(p, tools=[{"name": "lookup_price", "parameters": {"type": "object"}}])
    assert first.tool_calls[0]["provider_extra"] == {
        "extra_content": {"google": {"thought_signature": "SIG-abc123"}}
    }
    assert "provider_extra" not in first.tool_calls[1]

    history = [
        {"role": "user", "content": "price?"},
        {"role": "assistant", "content": None, "tool_calls": first.tool_calls},
        {"role": "tool", "tool_call_id": "c1", "content": "{}"},
        {"role": "tool", "tool_call_id": "c2", "content": "{}"},
    ]
    await call(p, messages=history, tools=[{"name": "lookup_price", "parameters": {"type": "object"}}])
    sent_calls = http.body(1)["messages"][2]["tool_calls"]
    assert sent_calls[0]["extra_content"] == {"google": {"thought_signature": "SIG-abc123"}}
    assert sent_calls[0]["function"]["name"] == "lookup_price" and "extra_content" not in sent_calls[1]
    assert "provider_extra" not in sent_calls[0]
