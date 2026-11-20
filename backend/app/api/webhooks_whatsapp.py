"""Meta WhatsApp webhook (CONTRACTS section 11, P3-2). URL: {PUBLIC_BASE_URL}/api/v1/webhooks/whatsapp

GET  verification handshake: hub.mode=subscribe & hub.verify_token == WHATSAPP_VERIFY_TOKEN → hub.challenge
POST events, signed with X-Hub-Signature-256 (HMAC-SHA256 of the raw body, key WHATSAPP_APP_SECRET; 401 if
     invalid). Routed to the tenant by metadata.phone_number_id → channel_connections. Idempotent
     (provider_message_id is unique), so Meta's retries are harmless. Answers 200 quickly: the reply pipeline
     runs in the worker (job_handle_inbound).
Only the webhook *parser* comes from the adapter module (pure functions); sending goes through the registry.
"""

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.channels.whatsapp_cloud import parse_webhook, verify_signature
from app.config import settings
from app.core.errors import AppError
from app.db import get_session
from app.services import messaging
from app.workers.queue import enqueue

logger = logging.getLogger("app.api.webhooks_whatsapp")

router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks"])


@router.get("", response_class=PlainTextResponse)
async def verify(
    mode: str | None = Query(None, alias="hub.mode"),
    token: str | None = Query(None, alias="hub.verify_token"),
    challenge: str | None = Query(None, alias="hub.challenge"),
) -> PlainTextResponse:
    expected = settings.WHATSAPP_VERIFY_TOKEN
    if mode == "subscribe" and expected and token == expected and challenge is not None:
        return PlainTextResponse(challenge)
    raise AppError("forbidden", "Webhook verification failed (check WHATSAPP_VERIFY_TOKEN).", 403)


def _check_signature(raw: bytes, header: str | None) -> None:
    secret = settings.WHATSAPP_APP_SECRET
    if not secret:
        if settings.USE_MOCK_ADAPTERS:
            logger.warning("WHATSAPP_APP_SECRET is not set; accepting an unsigned webhook (mock mode only)")
            return
        raise AppError(
            "unauthorized", "Webhook signature cannot be checked: WHATSAPP_APP_SECRET is not set.", 401
        )
    if not verify_signature(raw, header, secret):
        raise AppError("unauthorized", "Invalid webhook signature.", 401)


@router.post("")
async def receive(request: Request, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    raw = await request.body()
    _check_signature(raw, request.headers.get("X-Hub-Signature-256"))
    try:
        payload = json.loads(raw or b"{}")
    except ValueError as exc:
        raise AppError("invalid_payload", "The webhook body is not JSON.", 400) from exc
    inbound, statuses = parse_webhook(payload if isinstance(payload, dict) else {})

    stored: list[uuid.UUID] = []
    duplicates = unknown = updated = 0
    for item in inbound:
        try:
            outcome = await messaging.handle_inbound(session, item)
            await session.commit()
        except Exception:  # one bad event must not lose the others
            await session.rollback()
            logger.exception("whatsapp webhook: could not store an inbound message")
            continue
        if outcome.duplicate:
            duplicates += 1
        elif outcome.message is None:
            unknown += 1
        else:
            stored.append(outcome.message.id)
    for account, status in statuses:
        try:
            if await messaging.apply_status(session, account, status):
                updated += 1
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("whatsapp webhook: could not apply a status update")

    for message_id in stored:
        try:
            await enqueue("job_handle_inbound", message_id=str(message_id), _job_id=f"inbound:{message_id}")
        except Exception:
            logger.exception("could not enqueue job_handle_inbound for %s", message_id)
    return {
        "ok": True,
        "stored": len(stored),
        "duplicates": duplicates,
        "unknown": unknown,
        "statuses": updated,
    }
