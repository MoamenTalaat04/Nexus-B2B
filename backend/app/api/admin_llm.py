"""Super Admin API for managing dynamic LLM providers, API keys, models, and priority."""

import time
import uuid

import httpx
from fastapi import APIRouter, Depends, Header
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.crypto import CryptoError
from app.core.errors import AppError
from app.db import get_session
from app.models.llm_provider import LlmProviderConfig
from app.schemas.admin_llm import (
    LlmProviderCreate,
    LlmProviderListOut,
    LlmProviderOut,
    LlmProviderReorderIn,
    LlmProviderTestOut,
    LlmProviderUpdate,
)
from app.services.llm_registry import decrypt_api_key, encrypt_api_key, mask_api_key

router = APIRouter(prefix="/admin/llm-providers", tags=["admin-llm"])


def _require_super_admin(x_admin_role: str | None = Header(default=None, alias="X-Admin-Role")) -> None:
    if x_admin_role != "super_admin":
        raise AppError("forbidden", "Super Admin access required.", status_code=403)


def _to_out(row: LlmProviderConfig) -> LlmProviderOut:
    try:
        plain_key = decrypt_api_key(row.encrypted_api_key)
        masked = mask_api_key(plain_key)
    except CryptoError:
        masked = "****"
    return LlmProviderOut(
        id=row.id,
        name=row.name,
        provider_type=row.provider_type,
        base_url=row.base_url,
        api_key_masked=masked,
        model_smart=row.model_smart,
        model_fast=row.model_fast,
        reasoning_models=row.reasoning_models,
        priority=row.priority,
        is_active=row.is_active,
        is_primary=row.is_primary,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _list_rows(session: AsyncSession) -> list[LlmProviderConfig]:
    rows = list(
        (
            await session.execute(
                select(LlmProviderConfig).order_by(
                    LlmProviderConfig.is_primary.desc(),
                    LlmProviderConfig.priority.asc(),
                    LlmProviderConfig.created_at.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows and settings.LLM_API_KEY and settings.LLM_BASE_URL:
        provider_type = "groq" if "groq.com" in settings.LLM_BASE_URL else "custom"
        seeded = LlmProviderConfig(
            name="Groq (Default)" if provider_type == "groq" else "Default .env Provider",
            provider_type=provider_type,
            base_url=settings.LLM_BASE_URL,
            encrypted_api_key=encrypt_api_key(settings.LLM_API_KEY),
            model_smart=settings.LLM_MODEL_SMART,
            model_fast=settings.LLM_MODEL_FAST,
            reasoning_models=settings.LLM_REASONING_MODELS,
            priority=1,
            is_active=True,
            is_primary=True,
        )
        session.add(seeded)
        await session.commit()
        await session.refresh(seeded)
        rows = [seeded]
    return rows


@router.get("", response_model=LlmProviderListOut, dependencies=[Depends(_require_super_admin)])
async def list_llm_providers(session: AsyncSession = Depends(get_session)) -> LlmProviderListOut:
    rows = await _list_rows(session)
    return LlmProviderListOut(
        items=[_to_out(r) for r in rows],
        total=len(rows),
        env_fallback_model_smart=settings.LLM_MODEL_SMART,
        env_fallback_base_url=settings.LLM_BASE_URL,
    )


@router.post("", response_model=LlmProviderOut, status_code=201, dependencies=[Depends(_require_super_admin)])
async def create_llm_provider(
    body: LlmProviderCreate,
    session: AsyncSession = Depends(get_session),
) -> LlmProviderOut:
    if body.is_primary:
        await session.execute(update(LlmProviderConfig).values(is_primary=False))

    model_smart = body.model_smart.strip()
    model_fast = body.model_fast.strip() or model_smart

    row = LlmProviderConfig(
        name=body.name.strip(),
        provider_type=body.provider_type,
        base_url=body.base_url.strip().rstrip("/"),
        encrypted_api_key=encrypt_api_key(body.api_key.strip()),
        model_smart=model_smart,
        model_fast=model_fast,
        reasoning_models=body.reasoning_models.strip(),
        priority=body.priority,
        is_active=body.is_active,
        is_primary=body.is_primary,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _to_out(row)


@router.put("/{provider_id}", response_model=LlmProviderOut, dependencies=[Depends(_require_super_admin)])
async def update_llm_provider(
    provider_id: uuid.UUID,
    body: LlmProviderUpdate,
    session: AsyncSession = Depends(get_session),
) -> LlmProviderOut:
    row = await session.get(LlmProviderConfig, provider_id)
    if row is None:
        raise AppError("not_found", "LLM provider not found.", status_code=404)

    if body.is_primary is True:
        await session.execute(
            update(LlmProviderConfig).where(LlmProviderConfig.id != provider_id).values(is_primary=False)
        )

    if body.name is not None:
        row.name = body.name.strip()
    if body.provider_type is not None:
        row.provider_type = body.provider_type
    if body.base_url is not None:
        row.base_url = body.base_url.strip().rstrip("/")
    if body.api_key is not None:
        row.encrypted_api_key = encrypt_api_key(body.api_key.strip())
    if body.model_smart is not None:
        row.model_smart = body.model_smart.strip()
    if body.model_fast is not None:
        row.model_fast = body.model_fast.strip()
    if body.reasoning_models is not None:
        row.reasoning_models = body.reasoning_models.strip()
    if body.priority is not None:
        row.priority = body.priority
    if body.is_active is not None:
        row.is_active = body.is_active
    if body.is_primary is not None:
        row.is_primary = body.is_primary

    await session.commit()
    await session.refresh(row)
    return _to_out(row)


@router.post(
    "/{provider_id}/set-primary",
    response_model=LlmProviderOut,
    dependencies=[Depends(_require_super_admin)],
)
async def set_primary_llm_provider(
    provider_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> LlmProviderOut:
    row = await session.get(LlmProviderConfig, provider_id)
    if row is None:
        raise AppError("not_found", "LLM provider not found.", status_code=404)

    await session.execute(update(LlmProviderConfig).values(is_primary=False))
    row.is_primary = True
    row.is_active = True
    row.priority = 1
    await session.commit()
    await session.refresh(row)
    return _to_out(row)


def _friendly_http_error(status: int, detail: str = "") -> str:
    base = {
        401: "HTTP 401: Invalid API Key",
        403: "HTTP 403: Access forbidden for this API key",
        404: "HTTP 404: Model or endpoint not found",
        429: "HTTP 429: Rate limit or queue full",
        502: "HTTP 502: Gateway or upstream failure",
        503: "HTTP 503: Model unavailable",
    }.get(status, f"HTTP {status}")
    return f"{base} — {detail}" if detail else base


@router.post(
    "/{provider_id}/test",
    response_model=LlmProviderTestOut,
    dependencies=[Depends(_require_super_admin)],
)
async def test_llm_provider(
    provider_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> LlmProviderTestOut:
    row = await session.get(LlmProviderConfig, provider_id)
    if row is None:
        raise AppError("not_found", "LLM provider not found.", status_code=404)

    api_key = decrypt_api_key(row.encrypted_api_key)
    base_url = row.base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"}
    started = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0)) as client:
            # 1-3. Verify Base URL reachability, API key authentication, and model listing
            models_res = await client.get(f"{base_url}/models", headers=headers)
            if models_res.status_code >= 400:
                return LlmProviderTestOut(
                    ok=False,
                    status_code=models_res.status_code,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    error=_friendly_http_error(models_res.status_code),
                )

            models_payload = models_res.json() if models_res.content else {}
            model_items = models_payload.get("data", []) if isinstance(models_payload, dict) else []
            model_ids = [
                str(item.get("id", "")).strip()
                for item in model_items
                if isinstance(item, dict) and item.get("id")
            ]

            # 4. Verify the configured model identifier is listed (when /models returns a list)
            if model_ids and row.model_smart not in model_ids:
                return LlmProviderTestOut(
                    ok=False,
                    status_code=404,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    models_count=len(model_ids),
                    model_checked=row.model_smart,
                    error=f"HTTP 404: Configured model '{row.model_smart}' not found. Available: {', '.join(model_ids[:5])}",
                )

            # 5. Send a real non-streaming chat completion request
            chat_res = await client.post(
                f"{base_url}/chat/completions",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "model": row.model_smart,
                    "messages": [{"role": "user", "content": "Reply with OK only."}],
                    "max_tokens": 16,
                    "stream": False,
                },
            )
            latency_ms = int((time.perf_counter() - started) * 1000)

            if chat_res.status_code >= 400:
                err_msg = ""
                try:
                    err_json = chat_res.json()
                    if isinstance(err_json, dict):
                        err_obj = err_json.get("error", err_json)
                        err_msg = str(err_obj.get("message", "") if isinstance(err_obj, dict) else err_obj)[:200]
                except ValueError:
                    err_msg = chat_res.text[:200]
                return LlmProviderTestOut(
                    ok=False,
                    status_code=chat_res.status_code,
                    latency_ms=latency_ms,
                    models_count=len(model_ids),
                    model_checked=row.model_smart,
                    error=_friendly_http_error(chat_res.status_code, err_msg),
                )

            chat_payload = chat_res.json() if chat_res.content else {}
            choices = chat_payload.get("choices", []) if isinstance(chat_payload, dict) else []
            first_msg = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
            reply_text = str(first_msg.get("content") or "").strip()

            if not reply_text:
                return LlmProviderTestOut(
                    ok=False,
                    status_code=chat_res.status_code,
                    latency_ms=latency_ms,
                    models_count=len(model_ids),
                    model_checked=row.model_smart,
                    error="Provider returned HTTP 200 but an empty chat completion response.",
                )

            return LlmProviderTestOut(
                ok=True,
                status_code=chat_res.status_code,
                latency_ms=latency_ms,
                models_count=len(model_ids),
                model_checked=row.model_smart,
                reply_preview=reply_text[:80],
            )
    except httpx.TimeoutException:
        return LlmProviderTestOut(
            ok=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model_checked=row.model_smart,
            error="Connection timeout: the provider did not respond within 25s.",
        )
    except (httpx.ConnectError, httpx.RemoteProtocolError):
        return LlmProviderTestOut(
            ok=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model_checked=row.model_smart,
            error="Runtime disconnection or unreachable Base URL.",
        )
    except Exception:
        return LlmProviderTestOut(
            ok=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model_checked=row.model_smart,
            error="Unexpected connection error while testing provider.",
        )


@router.post(
    "/reorder",
    response_model=LlmProviderListOut,
    dependencies=[Depends(_require_super_admin)],
)
async def reorder_llm_providers(
    body: LlmProviderReorderIn,
    session: AsyncSession = Depends(get_session),
) -> LlmProviderListOut:
    rows = await _list_rows(session)
    by_id = {row.id: row for row in rows}
    ordered_rows: list[LlmProviderConfig] = []
    seen: set[uuid.UUID] = set()
    for pid in body.ordered_ids:
        if pid in by_id and pid not in seen:
            ordered_rows.append(by_id[pid])
            seen.add(pid)
    for row in rows:
        if row.id not in seen:
            ordered_rows.append(row)

    for idx, row in enumerate(ordered_rows):
        row.priority = idx + 1
        row.is_primary = idx == 0

    await session.commit()
    refreshed = await _list_rows(session)
    return LlmProviderListOut(
        items=[_to_out(r) for r in refreshed],
        total=len(refreshed),
        env_fallback_model_smart=settings.LLM_MODEL_SMART,
        env_fallback_base_url=settings.LLM_BASE_URL,
    )


@router.delete("/{provider_id}", status_code=204, dependencies=[Depends(_require_super_admin)])
async def delete_llm_provider(
    provider_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await session.get(LlmProviderConfig, provider_id)
    if row is None:
        raise AppError("not_found", "LLM provider not found.", status_code=404)
    await session.delete(row)
    await session.commit()
