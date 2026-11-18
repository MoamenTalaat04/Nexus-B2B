"""LLM provider for any OpenAI-compatible Chat Completions endpoint
(Gemini, Groq, OpenRouter, Ollama, OpenAI…).

Configured only through settings: LLM_BASE_URL, LLM_API_KEY, LLM_REASONING_MODELS, LLM_TIMEOUT_SECONDS.
This is the only module (with its siblings in app/adapters/llm/) allowed to import an LLM SDK.

Mapping from the neutral interface:
- system + cached_context → the first system message (stable, always first); the volatile messages follow, so
  providers that cache prompt prefixes can reuse it.
- json_schema → response_format json_schema with strict=true. If the provider rejects that
  (HTTP 400/422), this model falls back for the rest of the process to response_format json_object,
  with the schema described in the system message. The wrapper validates the answer with Pydantic either way.
- tools → the "function" tool format, tool_choice "auto"; tool_call arguments are parsed from JSON.
- effort → reasoning_effort, only for models listed in LLM_REASONING_MODELS.
- The SDK's own retries are off: app.agents.llm owns retries, backoff and the concurrency cap.
"""

import json
import logging
import re
from typing import TYPE_CHECKING, Any

import openai
from openai import AsyncOpenAI

from app.adapters.llm.base import Effort, Finish, LLMProviderError, LLMResult, LLMUsage
from app.config import settings

if TYPE_CHECKING:
    import httpx2

logger = logging.getLogger("app.llm.openai_compatible")

_RETRYABLE_STATUS = {408, 409, 429}


def _schema_name(schema: dict[str, Any]) -> str:
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", str(schema.get("title") or "output"))
    return name[:64] or "output"


def _schema_instructions(schema: dict[str, Any]) -> str:
    return (
        "Reply with only one JSON object (no prose, no code fences) that matches this JSON schema:\n"
        + json.dumps(schema, ensure_ascii=False)
    )


def _to_openai_message(message: dict[str, Any]) -> dict[str, Any]:
    role = message["role"]
    if role == "assistant" and message.get("tool_calls"):
        return {
            "role": "assistant",
            "content": message.get("content"),
            "tool_calls": [
                {
                    **(
                        call.get("provider_extra") or {}
                    ),  # e.g. Gemini's thought signature, sent back as received
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call.get("arguments", {}), ensure_ascii=False),
                    },
                }
                for call in message["tool_calls"]
            ],
        }
    if role == "tool":
        return {"role": "tool", "tool_call_id": message["tool_call_id"], "content": message["content"]}
    return {"role": role, "content": message.get("content", "")}


def _parse_arguments(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"_invalid_json": raw}
    return parsed if isinstance(parsed, dict) else {"_value": parsed}


_TOOL_CALL_FIELDS = {"id", "type", "function"}


def _tool_call(call: Any) -> dict[str, Any]:
    """Neutral tool call. Unknown provider fields are kept in `provider_extra` and sent back unchanged on the
    next turn: Gemini 3+ requires its `extra_content.google.thought_signature` to come back, or it rejects
    the follow-up request with HTTP 400."""
    raw = call.model_dump() if hasattr(call, "model_dump") else {}
    extra = {k: v for k, v in raw.items() if k not in _TOOL_CALL_FIELDS and v is not None}
    result: dict[str, Any] = {
        "id": call.id,
        "name": call.function.name,
        "arguments": _parse_arguments(call.function.arguments),
    }
    if extra:
        result["provider_extra"] = extra
    return result


def _retry_after(exc: openai.APIStatusError) -> float | None:
    value = exc.response.headers.get("retry-after") if exc.response is not None else None
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _map_error(exc: Exception) -> LLMProviderError:
    if isinstance(exc, openai.APIConnectionError):  # includes timeouts
        return LLMProviderError(f"connection error: {exc}", retryable=True)
    if isinstance(exc, openai.APIStatusError):
        status = exc.status_code
        retryable = status in _RETRYABLE_STATUS or status >= 500
        return LLMProviderError(
            f"provider returned HTTP {status}: {exc.message}",
            retryable=retryable,
            status_code=status,
            retry_after=_retry_after(exc) if retryable else None,
        )
    return LLMProviderError(f"unexpected provider error: {exc}", retryable=False)


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float,
        reasoning_models: set[str],
        http_client: "httpx2.AsyncClient | None" = None,  # tests inject a mock transport here
    ) -> None:
        self._client = AsyncOpenAI(
            base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0, http_client=http_client
        )
        self._reasoning_models = reasoning_models
        self._no_strict_schema: set[str] = set()  # models that rejected strict json_schema

    @classmethod
    def from_settings(cls) -> "OpenAICompatibleProvider":
        models = {m.strip() for m in settings.LLM_REASONING_MODELS.split(",") if m.strip()}
        return cls(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            reasoning_models=models,
        )

    def _request(
        self,
        *,
        model: str,
        system: str,
        cached_context: str | None,
        messages: list[dict[str, Any]],
        effort: Effort,
        max_tokens: int,
        json_schema: dict[str, Any] | None,
        tools: list[dict[str, Any]] | None,
        strict: bool,
    ) -> dict[str, Any]:
        system_text = system if not cached_context else f"{system}\n\n{cached_context}"
        if json_schema is not None and not strict:
            system_text = f"{system_text}\n\n{_schema_instructions(json_schema)}"
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system_text}]
            + [_to_openai_message(m) for m in messages],
        }
        if model in self._reasoning_models:
            body["reasoning_effort"] = effort
            body["max_completion_tokens"] = max_tokens
        else:
            body["max_tokens"] = max_tokens
        if json_schema is not None:
            body["response_format"] = (
                {
                    "type": "json_schema",
                    "json_schema": {"name": _schema_name(json_schema), "schema": json_schema, "strict": True},
                }
                if strict
                else {"type": "json_object"}
            )
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t["parameters"],
                    },
                }
                for t in tools
            ]
            body["tool_choice"] = "auto"
        return body

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
    ) -> LLMResult:
        strict = json_schema is not None and model not in self._no_strict_schema
        args: dict[str, Any] = {
            "model": model,
            "system": system,
            "cached_context": cached_context,
            "messages": messages,
            "effort": effort,
            "max_tokens": max_tokens,
            "json_schema": json_schema,
            "tools": tools,
        }
        try:
            response = await self._client.chat.completions.create(**self._request(**args, strict=strict))
        except (openai.BadRequestError, openai.UnprocessableEntityError) as exc:
            if not strict:
                raise _map_error(exc) from exc
            logger.info("model %s rejected strict json_schema; falling back to json_object", model)
            self._no_strict_schema.add(model)
            try:
                response = await self._client.chat.completions.create(**self._request(**args, strict=False))
            except openai.OpenAIError as exc2:
                raise _map_error(exc2) from exc2
        except openai.OpenAIError as exc:
            raise _map_error(exc) from exc
        return self._to_result(response, model)

    @staticmethod
    def _to_result(response: Any, requested_model: str) -> LLMResult:
        if not response.choices:
            raise LLMProviderError("provider returned no choices", retryable=True)
        choice = response.choices[0]
        message = choice.message
        tool_calls = [
            _tool_call(call) for call in (message.tool_calls or []) if getattr(call, "function", None)
        ]
        reason = choice.finish_reason
        finish: Finish
        if getattr(message, "refusal", None) or reason == "content_filter":
            finish = "refused"
        elif reason == "length":
            finish = "length"
        elif reason == "tool_calls" or tool_calls:  # some providers report "stop" next to tool calls
            finish = "tool_calls"
        else:
            finish = "stop"

        usage = response.usage
        cached = 0
        if usage is not None and usage.prompt_tokens_details is not None:
            cached = usage.prompt_tokens_details.cached_tokens or 0
        return LLMResult(
            text=message.content,
            tool_calls=tool_calls,
            finish=finish,
            usage=LLMUsage(
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                cached_input_tokens=cached,
            ),
            model=response.model or requested_model,
            raw=response.model_dump(mode="json"),
        )
