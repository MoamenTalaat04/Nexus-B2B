"""WhatsApp Cloud API (Meta Graph API) as a ChannelAdapter (P3-2). Official API only, never WhatsApp Web.

Endpoints (Graph version from settings.WHATSAPP_GRAPH_VERSION, e.g. "v27.0"):
- POST /{phone_number_id}/messages                      send a template or a text (24h window only)
- GET  /{phone_number_id}?fields=display_phone_number,…  check_connection
- GET  /{waba_id}/message_templates                     list_templates (paged)
Errors: Graph returns {"error": {"code", "message", "error_subcode", "error_data": {"details"}}}; codes are
mapped to short readable SendResult.error values (see ERROR_CODES). Only 429/5xx/transport errors are retried
(with backoff); a 4xx is final.

This module also holds the webhook helpers: signature verification and parse_webhook() → InboundMessage /
StatusUpdate (both from CONTRACTS section 7), plus builders for test payloads.

No tracing here (adapters have no RunContext); services/messaging records the EXTERNAL_API step.
Never log the access token or full message bodies.
"""

import asyncio
import hashlib
import hmac
import logging
import random
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.adapters.base import InboundMessage, SendResult, StatusUpdate, TemplateInfo
from app.config import settings
from app.models.enums import ChannelType, MessageStatus

logger = logging.getLogger("app.adapters.whatsapp_cloud")

GRAPH_BASE = "https://graph.facebook.com"
DEFAULT_GRAPH_VERSION = "v27.0"
MAX_RETRIES = 3
TIMEOUT_SECONDS = 20.0

# Meta error code → our short error code (SendResult.error / messages.error prefix).
ERROR_CODES: dict[int, str] = {
    190: "invalid_token",  # access token expired/invalid
    10: "permission_denied",
    200: "permission_denied",
    4: "rate_limited",
    80007: "rate_limited",
    130429: "rate_limited",
    131056: "rate_limited",  # too many messages to the same recipient
    131030: "recipient_not_allowed",  # test numbers: recipient not in the allowed list
    131047: "window_closed",  # re-engagement: more than 24h since the customer's last message
    132000: "template_param_mismatch",
    132001: "template_not_approved",  # does not exist in this language or not approved
    132005: "template_too_long",
    132007: "template_policy_violation",
    132012: "template_param_format",
    132015: "template_paused",
    132016: "template_disabled",
    131026: "undeliverable",  # not on WhatsApp, blocked the business, old app …
    131049: "marketing_limit",  # per-user marketing template limit
    131051: "unsupported_message_type",
    133010: "phone_not_registered",
    368: "account_restricted",
    100: "invalid_parameter",
    131000: "provider_error",
    131016: "provider_unavailable",
}
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

_PARAM_SANITIZE_RE = re.compile(r"[\r\n\t]+")
_SPACES_RE = re.compile(r" {5,}")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


class WhatsAppError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def digits(phone_e164: str) -> str:
    """Graph wants the recipient as digits with the country code, no "+"."""
    return "".join(ch for ch in phone_e164 if ch.isdigit())


def sanitize_param(value: str) -> str:
    """Template params may not contain newlines/tabs or more than 4 consecutive spaces (Meta rule)."""
    cleaned = _PARAM_SANITIZE_RE.sub(" ", str(value))
    cleaned = _SPACES_RE.sub("    ", cleaned).strip()
    return cleaned or "-"


def count_params(body_text: str) -> int:
    return len(set(_PLACEHOLDER_RE.findall(body_text or "")))


def map_error(payload: Any, status_code: int | None = None) -> tuple[str, str]:
    """(short code, readable message) from a Graph error payload."""
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return ("provider_error", f"WhatsApp API error (HTTP {status_code})")
    code = error.get("code")
    details = (
        (error.get("error_data") or {}).get("details") if isinstance(error.get("error_data"), dict) else None
    )
    message = str(error.get("message") or "WhatsApp API error")
    if details:
        message = f"{message} — {details}"
    short = ERROR_CODES.get(int(str(code))) if isinstance(code, int) or str(code).isdigit() else None
    return (short or "provider_error", f"{message} (code {code})")


def _graph_version() -> str:
    return settings.WHATSAPP_GRAPH_VERSION or DEFAULT_GRAPH_VERSION


class WhatsAppCloudAdapter:
    channel = ChannelType.WHATSAPP

    def __init__(
        self,
        *,
        phone_number_id: str,
        waba_id: str,
        access_token: str,
        client: httpx.AsyncClient | None = None,
        graph_version: str | None = None,
    ) -> None:
        self.phone_number_id = phone_number_id
        self.waba_id = waba_id
        self._token = access_token
        self._client = client
        self._version = graph_version or _graph_version()
        self._sleep = asyncio.sleep

    def __repr__(self) -> str:  # never show the token
        return f"WhatsAppCloudAdapter(phone_number_id={self.phone_number_id!r})"

    # ------------------------------------------------------------------------------------------ http

    def _url(self, path: str) -> str:
        return f"{GRAPH_BASE}/{self._version}/{path.lstrip('/')}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Returns the JSON body; raises WhatsAppError(code, message) on any final failure."""
        headers = {"Authorization": f"Bearer {self._token}"}
        client = self._client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
        try:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    response = await client.request(
                        method, self._url(path), json=json, params=params, headers=headers
                    )
                except httpx.TransportError as exc:
                    if attempt < MAX_RETRIES:
                        await self._sleep(self._backoff(attempt))
                        continue
                    raise WhatsAppError(
                        "provider_unreachable", f"Could not reach the WhatsApp API: {exc}"
                    ) from exc
                if response.status_code < 400:
                    try:
                        data: dict[str, Any] = response.json()
                    except ValueError:
                        data = {}
                    return data
                try:
                    payload = response.json()
                except ValueError:
                    payload = None
                code, message = map_error(payload, response.status_code)
                if response.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                    logger.warning(
                        "whatsapp: HTTP %s (%s), retry %d/%d",
                        response.status_code,
                        code,
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    await self._sleep(self._backoff(attempt))
                    continue
                raise WhatsAppError(code, message)
        finally:
            if self._client is None:
                await client.aclose()
        raise AssertionError("unreachable")  # pragma: no cover

    @staticmethod
    def _backoff(attempt: int) -> float:
        return float(2**attempt) + random.uniform(0, 0.5)

    # ------------------------------------------------------------------------------------------ API

    async def _send(self, body: dict[str, Any]) -> SendResult:
        try:
            data = await self._request("POST", f"{self.phone_number_id}/messages", json=body)
        except WhatsAppError as exc:
            # known Meta codes → the short code ("window_closed", "recipient_not_allowed" …)
            return SendResult(
                ok=False, error=exc.code if exc.code != "provider_error" else f"provider_error: {exc}"
            )
        messages = data.get("messages") or []
        provider_id = messages[0].get("id") if messages and isinstance(messages[0], dict) else None
        if not provider_id:
            return SendResult(ok=False, error="provider_error: no message id in the response")
        return SendResult(ok=True, provider_message_id=str(provider_id))

    async def send_template(
        self, *, to: str, template_name: str, language: str, params: list[str]
    ) -> SendResult:
        clean = [sanitize_param(p) for p in params]
        if clean != [str(p) for p in params]:
            logger.info("whatsapp: sanitised template params for %s (newlines/tabs/spaces)", template_name)
        template: dict[str, Any] = {"name": template_name, "language": {"code": language}}
        if clean:
            template["components"] = [
                {"type": "body", "parameters": [{"type": "text", "text": value} for value in clean]}
            ]
        return await self._send(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": digits(to),
                "type": "template",
                "template": template,
            }
        )

    async def send_text(self, *, to: str, body: str) -> SendResult:
        return await self._send(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": digits(to),
                "type": "text",
                "text": {"preview_url": False, "body": body[:4096]},
            }
        )

    async def check_connection(self) -> tuple[bool, str]:
        try:
            data = await self._request(
                "GET",
                self.phone_number_id,
                params={"fields": "display_phone_number,verified_name,quality_rating"},
            )
        except WhatsAppError as exc:
            return False, f"{exc.code}: {exc}"
        number = data.get("display_phone_number")
        if not number:
            return False, "provider_error: the phone number id did not return a display number"
        return True, str(number)

    async def phone_details(self) -> dict[str, Any]:
        """display_phone_number, verified_name, quality_rating (for the Channels page)."""
        try:
            return await self._request(
                "GET",
                self.phone_number_id,
                params={"fields": "display_phone_number,verified_name,quality_rating"},
            )
        except WhatsAppError:
            return {}

    async def list_templates(self) -> list[TemplateInfo]:
        templates: list[TemplateInfo] = []
        params: dict[str, Any] | None = {"fields": "name,language,status,category,components", "limit": 100}
        path = f"{self.waba_id}/message_templates"
        for _ in range(20):  # paging guard
            data = await self._request("GET", path, params=params)
            for item in data.get("data") or []:
                body = next(
                    (c.get("text", "") for c in item.get("components") or [] if c.get("type") == "BODY"), ""
                )
                templates.append(
                    TemplateInfo(
                        name=str(item.get("name")),
                        language=str(item.get("language") or "ar"),
                        category=str(item.get("category") or "MARKETING"),
                        status=str(item.get("status") or "PENDING"),
                        body_text=body,
                        param_count=count_params(body),
                    )
                )
            after = ((data.get("paging") or {}).get("cursors") or {}).get("after")
            if not after or not (data.get("paging") or {}).get("next"):
                break
            params = {"fields": "name,language,status,category,components", "limit": 100, "after": after}
        return templates


# ---------------------------------------------------------------------------------------------- webhooks


def verify_signature(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    """X-Hub-Signature-256: "sha256=<hex HMAC-SHA256 of the raw body, keyed by the app secret>"."""
    if not header or not app_secret or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256=").strip())


def sign(raw_body: bytes, app_secret: str) -> str:
    """The header value Meta would send (for tests and local simulation)."""
    return "sha256=" + hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()


_STATUS_MAP = {
    "sent": MessageStatus.SENT,
    "delivered": MessageStatus.DELIVERED,
    "read": MessageStatus.READ,
    "failed": MessageStatus.FAILED,
}
NON_TEXT_LABELS = {
    "image": "[image]",
    "audio": "[voice]",
    "voice": "[voice]",
    "video": "[video]",
    "document": "[document]",
    "sticker": "[sticker]",
    "location": "[location]",
    "contacts": "[contact]",
    "reaction": "[reaction]",
    "unsupported": "[unsupported]",
}


def _ts(value: Any) -> datetime:
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


def _message_text(msg: dict[str, Any]) -> str:
    kind = str(msg.get("type") or "")
    if kind == "text":
        return str((msg.get("text") or {}).get("body") or "")
    if kind == "button":
        return str((msg.get("button") or {}).get("text") or "[button]")
    if kind == "interactive":
        inter = msg.get("interactive") or {}
        reply = inter.get("button_reply") or inter.get("list_reply") or {}
        return str(reply.get("title") or "[interactive]")
    label = NON_TEXT_LABELS.get(kind, f"[{kind or 'unknown'}]")
    caption = (msg.get(kind) or {}).get("caption") if isinstance(msg.get(kind), dict) else None
    return f"{label} {caption}".strip() if caption else label


def parse_webhook(payload: dict[str, Any]) -> tuple[list[InboundMessage], list[tuple[str, StatusUpdate]]]:
    """Meta webhook body → (inbound messages, [(phone_number_id, status update)]); unknown parts ignored."""
    inbound: list[InboundMessage] = []
    statuses: list[tuple[str, StatusUpdate]] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            if change.get("field") != "messages":
                continue
            value = change.get("value") or {}
            account = str((value.get("metadata") or {}).get("phone_number_id") or "")
            for msg in value.get("messages") or []:
                if not msg.get("id") or not msg.get("from"):
                    continue
                inbound.append(
                    InboundMessage(
                        channel=ChannelType.WHATSAPP,
                        account_ref=account,
                        from_phone="+" + digits(str(msg["from"])),
                        provider_message_id=str(msg["id"]),
                        text=_message_text(msg),
                        timestamp=_ts(msg.get("timestamp")),
                        raw={"type": msg.get("type"), "context": msg.get("context")},
                    )
                )
            for st in value.get("statuses") or []:
                status = _STATUS_MAP.get(str(st.get("status")))
                if status is None or not st.get("id"):
                    continue
                error = None
                if st.get("errors"):
                    first = st["errors"][0] or {}
                    code = first.get("code")
                    short = ERROR_CODES.get(int(str(code))) if str(code).isdigit() else None
                    title = first.get("title") or first.get("message") or "failed"
                    error = f"{short or 'provider_error'}: {title} (code {code})"
                statuses.append(
                    (
                        account,
                        StatusUpdate(
                            provider_message_id=str(st["id"]),
                            status=status,
                            error=error,
                            timestamp=_ts(st.get("timestamp")),
                        ),
                    )
                )
    return inbound, statuses


def inbound_payload(
    *,
    phone_number_id: str,
    from_phone: str,
    text: str,
    message_id: str,
    timestamp: datetime | None = None,
    kind: str = "text",
) -> dict[str, Any]:
    """A Meta-shaped webhook body for one inbound message (tests, local simulation)."""
    ts = int((timestamp or datetime.now(UTC)).timestamp())
    msg: dict[str, Any] = {"from": digits(from_phone), "id": message_id, "timestamp": str(ts), "type": kind}
    if kind == "text":
        msg["text"] = {"body": text}
    else:
        msg[kind] = {"id": "media-1", "caption": text} if text else {"id": "media-1"}
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550000000",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [{"profile": {"name": "Test"}, "wa_id": digits(from_phone)}],
                            "messages": [msg],
                        },
                    }
                ],
            }
        ],
    }


def status_payload(
    *,
    phone_number_id: str,
    message_id: str,
    status: str,
    timestamp: datetime | None = None,
    error_code: int | None = None,
) -> dict[str, Any]:
    ts = int((timestamp or datetime.now(UTC)).timestamp())
    st: dict[str, Any] = {
        "id": message_id,
        "status": status,
        "timestamp": str(ts),
        "recipient_id": "201000000000",
    }
    if error_code is not None:
        st["errors"] = [{"code": error_code, "title": "Message failed"}]
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550000000",
                                "phone_number_id": phone_number_id,
                            },
                            "statuses": [st],
                        },
                    }
                ],
            }
        ],
    }
