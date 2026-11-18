"""Provider-neutral LLM interface (CONTRACTS section 6, "Provider adapters").

`app.agents.llm` talks only to an `LLMProvider`; concrete providers live next to this file.
Messages use one neutral shape:
    {"role": "user" | "assistant", "content": str}
    {"role": "assistant", "content": str | None, "tool_calls": [{"id", "name", "arguments": dict}]}
    {"role": "tool", "tool_call_id": str, "content": str}
"""

from typing import Any, Literal, Protocol

from pydantic import BaseModel

Effort = Literal["low", "medium", "high"]
Finish = Literal["stop", "tool_calls", "length", "refused"]


class LLMUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0


class LLMResult(BaseModel):
    text: str | None  # final text (None when the model only called tools)
    tool_calls: list[dict[str, Any]]  # [{"id", "name", "arguments": dict}]
    finish: Finish
    usage: LLMUsage
    model: str
    raw: dict[str, Any]  # provider response, for the trace


class LLMProvider(Protocol):
    name: str

    async def complete(
        self,
        *,
        model: str,
        system: str,
        cached_context: str | None,
        messages: list[dict[str, Any]],
        effort: Effort,
        max_tokens: int,
        json_schema: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResult: ...


class LLMConfigError(RuntimeError):
    """The LLM settings are missing or invalid (unknown provider, no base URL or key)."""


class LLMProviderError(Exception):
    """A provider call failed. `retryable` is True for rate limits, server errors and connection problems."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.retry_after = retry_after
