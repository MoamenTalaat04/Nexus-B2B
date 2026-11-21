"""Dynamic LLM provider registry backed by PostgreSQL with .env fallback."""

import logging
from dataclasses import dataclass

from sqlalchemy import select

from app.adapters.llm.openai_compatible import OpenAICompatibleProvider
from app.config import settings
from app.core.crypto import CryptoError, decrypt_json, encrypt_json
from app.db import SessionLocal
from app.models.llm_provider import LlmProviderConfig

logger = logging.getLogger("app.services.llm_registry")


@dataclass(frozen=True)
class ResolvedLlmTarget:
    name: str
    provider: OpenAICompatibleProvider
    model_smart: str
    model_fast: str


def encrypt_api_key(api_key: str) -> str:
    return encrypt_json({"api_key": api_key})


def decrypt_api_key(token: str) -> str:
    data = decrypt_json(token)
    return str(data.get("api_key", ""))


def mask_api_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:6]}...{api_key[-4:]}"


async def get_active_llm_targets() -> list[ResolvedLlmTarget]:
    """Load active DB LLM providers ordered by is_primary DESC, priority ASC."""
    try:
        async with SessionLocal() as session:
            rows = (
                (
                    await session.execute(
                        select(LlmProviderConfig)
                        .where(LlmProviderConfig.is_active.is_(True))
                        .order_by(
                            LlmProviderConfig.is_primary.desc(),
                            LlmProviderConfig.priority.asc(),
                            LlmProviderConfig.created_at.asc(),
                        )
                    )
                )
                .scalars()
                .all()
            )
    except Exception:
        # In unit tests without the table or during startup fallback, use .env settings.
        return []

    targets: list[ResolvedLlmTarget] = []
    for row in rows:
        try:
            api_key = decrypt_api_key(row.encrypted_api_key)
        except CryptoError:
            logger.warning("Skipping LLM provider %s: cannot decrypt API key", row.name)
            continue
        if not api_key or not row.base_url:
            continue
        reasoning = {m.strip() for m in row.reasoning_models.split(",") if m.strip()}
        provider = OpenAICompatibleProvider(
            base_url=row.base_url,
            api_key=api_key,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            reasoning_models=reasoning,
        )
        targets.append(
            ResolvedLlmTarget(
                name=row.name,
                provider=provider,
                model_smart=row.model_smart,
                model_fast=row.model_fast,
            )
        )
    return targets
