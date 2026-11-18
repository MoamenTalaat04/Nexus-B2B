"""LLM price table and cost calculation (CONTRACTS section 6).

Prices are USD per 1M tokens, keyed by the exact model id used in LLM_MODEL_SMART / LLM_MODEL_FAST.

Free-tier usage is priced at the provider's **paid** list price, so the reports show what the same work
would cost at scale. Every cost is therefore an *estimate* (`COSTS_ARE_ESTIMATES`),
and the UI labels it that way.

HOW TO ADD A MODEL: when a model id is chosen for .env, copy its paid list price from the provider's official
pricing page and add an entry below with a comment naming the source page and the date you checked it.
Never guess a price. An unknown model costs 0 and logs a warning once.
"""

import logging
from dataclasses import dataclass

from app.adapters.llm.base import LLMUsage

logger = logging.getLogger("app.llm.pricing")

COSTS_ARE_ESTIMATES = True


@dataclass(frozen=True)
class ModelPrice:
    input: float  # USD per 1M uncached input tokens
    output: float  # USD per 1M output tokens
    cached_input: float  # USD per 1M cached input tokens


PRICES: dict[str, ModelPrice] = {
    # "<model id>": ModelPrice(input=..., output=..., cached_input=...),
    # ^ add the source page URL and the date you checked it
    #
    # Google Gemini, paid "Standard" tier, text input. Source: https://aistudio.google.com/docs/pricing,
    # checked 2026-11-18. Cached-input storage fees are not included.
    "gemini-4-hydrogen": ModelPrice(input=1.50, output=7.50, cached_input=0.075),  # suggested SMART
    "gemini-3.5-flash-lite": ModelPrice(input=0.30, output=2.50, cached_input=0.03),  # suggested FAST
    "mock": ModelPrice(input=0.0, output=0.0, cached_input=0.0),
}

_warned: set[str] = set()


def price_for(model: str) -> ModelPrice | None:
    return PRICES.get(model)


def cost_usd(model: str, usage: LLMUsage) -> float:
    """Estimated cost of one call. Cached input tokens are part of input_tokens and billed at the cached
    price."""
    price = price_for(model)
    if price is None:
        if model not in _warned:
            _warned.add(model)
            logger.warning(
                "pricing: no price for model %r; its cost is recorded as 0 (add it to PRICES)", model
            )
        return 0.0
    cached = min(usage.cached_input_tokens, usage.input_tokens)
    uncached = usage.input_tokens - cached
    total = uncached * price.input + cached * price.cached_input + usage.output_tokens * price.output
    return round(total / 1_000_000, 6)
