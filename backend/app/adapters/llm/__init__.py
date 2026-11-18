"""LLM provider adapters (CONTRACTS section 6). `get_llm_provider()` returns the one chosen by settings.

To add a provider: create a module here with a class implementing `LLMProvider` (see base.py) and a
`from_settings()` classmethod, then add it to `_PROVIDERS`. No agent code changes.
"""

from app.adapters.llm.base import (
    Effort,
    LLMConfigError,
    LLMProvider,
    LLMProviderError,
    LLMResult,
    LLMUsage,
)
from app.config import settings

_PROVIDERS = ("openai_compatible",)
_cache: dict[tuple[str, str, str, str, float], LLMProvider] = {}


def get_llm_provider() -> LLMProvider:
    """The provider named by settings.LLM_PROVIDER (cached per configuration)."""
    name = settings.LLM_PROVIDER.strip()
    if name not in _PROVIDERS:
        raise LLMConfigError(f"Unknown LLM_PROVIDER {name!r}. Known providers: {', '.join(_PROVIDERS)}.")
    missing = [var for var in ("LLM_BASE_URL", "LLM_API_KEY") if not getattr(settings, var)]
    if missing:
        raise LLMConfigError(
            f"{' and '.join(missing)} must be set for LLM_PROVIDER={name} "
            "(see .env.example and docs/setup-accounts.md), or set USE_MOCK_LLM=true."
        )
    key = (
        name,
        settings.LLM_BASE_URL,
        settings.LLM_API_KEY,
        settings.LLM_REASONING_MODELS,
        settings.LLM_TIMEOUT_SECONDS,
    )
    if key not in _cache:
        from app.adapters.llm.openai_compatible import OpenAICompatibleProvider

        _cache[key] = OpenAICompatibleProvider.from_settings()
    return _cache[key]


__all__ = [
    "Effort",
    "LLMConfigError",
    "LLMProvider",
    "LLMProviderError",
    "LLMResult",
    "LLMUsage",
    "get_llm_provider",
]
