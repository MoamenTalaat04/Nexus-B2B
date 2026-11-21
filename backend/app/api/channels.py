"""Channels API (CONTRACTS section 11, P3-2). D's Settings → Channels page is built on these routes.

GET  /api/v1/channels                              → {"items": [ChannelOut], "webhook_url": str}
PUT  /api/v1/channels/whatsapp {phone_number_id, waba_id, access_token}
                                                   → ChannelOut (status "connected" or "error" + last_error)
POST /api/v1/channels/whatsapp/test {to}           → TestSendOut (hello_world, or the first approved template)
POST /api/v1/channels/whatsapp/templates/sync      → {"items": [TemplateOut], "total": n}
PUT  /api/v1/channels/whatsapp/templates/{id} {purpose: "intro"|"followup"|null}
                                                   → TemplateOut (the owner tags what each template is for)
The access token is stored encrypted (app.core.crypto) and is never returned. Only owners can change channels.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import registry
from app.config import settings as app_settings
from app.core.crypto import CryptoError, encrypt_json
from app.core.errors import AppError, NotFoundError
from app.core.phones import normalize_eg_phone
from app.core.security import CurrentUser, get_current_user
from app.core.tenancy import get_settings_for
from app.db import get_session
from app.models.enums import ChannelType
from app.models.messaging import ChannelConnection, MessageTemplate
from app.services.messaging import get_whatsapp_connection

router = APIRouter(prefix="/channels", tags=["channels"])

META_STATUS = {
    "APPROVED": "approved",
    "PENDING": "pending",
    "IN_APPEAL": "pending",
}  # anything else: rejected
DEFAULT_PURPOSE_BY_NAME = {"intro": "intro", "followup": "followup", "follow_up": "followup"}


class TemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    language: str
    category: str
    status: str  # approved | pending | rejected
    purpose: str | None  # intro | followup | null (not used by the agent)
    body_text: str
    param_count: int


class ChannelOut(BaseModel):
    channel: str
    status: str  # connected | error | disconnected
    phone_number_id: str | None = None
    waba_id: str | None = None
    display_phone_number: str | None = None
    verified_name: str | None = None
    quality_rating: str | None = None
    last_checked_at: datetime | None = None
    last_error: str | None = None
    templates: list[TemplateOut] = Field(default_factory=list)


class ChannelsOut(BaseModel):
    items: list[ChannelOut]
    webhook_url: str
    verify_token_configured: bool
    app_secret_configured: bool


class WhatsAppConnectIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    phone_number_id: str = Field(min_length=5, max_length=40, pattern=r"^\d+$")
    waba_id: str = Field(min_length=5, max_length=40, pattern=r"^\d+$")
    access_token: str = Field(min_length=20, max_length=1000)


class TestSendIn(BaseModel):
    to: str


class TestSendOut(BaseModel):
    ok: bool
    to: str
    template_name: str
    provider_message_id: str | None
    error: str | None


class TemplateList(BaseModel):
    items: list[TemplateOut]
    total: int


class TemplatePurposeIn(BaseModel):
    purpose: Literal["intro", "followup"] | None


def webhook_url() -> str:
    return f"{app_settings.PUBLIC_BASE_URL.rstrip('/')}/api/v1/webhooks/whatsapp"


def _owner(user: CurrentUser) -> None:
    if user.role != "owner":
        raise AppError("forbidden", "Only the account owner can change channels.", status_code=403)


def _template_out(t: MessageTemplate) -> TemplateOut:
    return TemplateOut(
        id=t.id,
        name=t.name,
        language=t.language,
        category=t.category,
        status=t.status,
        purpose=t.purpose,
        body_text=t.body_text,
        param_count=t.param_count,
    )


async def _templates(session: AsyncSession, tenant_id: uuid.UUID) -> list[MessageTemplate]:
    rows = await session.execute(
        select(MessageTemplate)
        .where(MessageTemplate.tenant_id == tenant_id, MessageTemplate.channel == ChannelType.WHATSAPP.value)
        .order_by(MessageTemplate.name, MessageTemplate.language)
    )
    return list(rows.scalars())


async def _channel_out(
    session: AsyncSession, tenant_id: uuid.UUID, row: ChannelConnection | None
) -> ChannelOut:
    templates = [_template_out(t) for t in await _templates(session, tenant_id)]
    if row is None:
        return ChannelOut(channel=ChannelType.WHATSAPP.value, status="disconnected", templates=templates)
    config: dict[str, Any] = row.config or {}
    return ChannelOut(
        channel=row.channel,
        status=row.status,
        phone_number_id=config.get("phone_number_id"),
        waba_id=config.get("waba_id"),
        display_phone_number=config.get("display_phone_number"),
        verified_name=config.get("verified_name"),
        quality_rating=config.get("quality_rating"),
        last_checked_at=row.last_checked_at,
        last_error=row.last_error,
        templates=templates,
    )


async def sync_templates(session: AsyncSession, tenant_id: uuid.UUID) -> list[MessageTemplate]:
    """Upsert message_templates from Meta (by name + language). Owner-set purposes are kept."""
    adapter = await registry.get_channel(session, tenant_id, ChannelType.WHATSAPP)
    remote = await adapter.list_templates()
    existing = {(t.name, t.language): t for t in await _templates(session, tenant_id)}
    for info in remote:
        status = META_STATUS.get(info.status.upper(), "rejected")
        row = existing.get((info.name, info.language))
        if row is None:
            row = MessageTemplate(
                tenant_id=tenant_id,
                channel=ChannelType.WHATSAPP.value,
                name=info.name,
                language=info.language,
                purpose=DEFAULT_PURPOSE_BY_NAME.get(info.name.lower()),
            )
            session.add(row)
        row.category = info.category
        row.status = status
        row.body_text = info.body_text
        row.param_count = info.param_count
    await session.flush()
    return await _templates(session, tenant_id)


# ---------------------------------------------------------------------------------------------- routes


@router.get("", response_model=ChannelsOut)
async def list_channels(
    user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> ChannelsOut:
    row = await get_whatsapp_connection(session, user.tenant_id)
    return ChannelsOut(
        items=[await _channel_out(session, user.tenant_id, row)],
        webhook_url=webhook_url(),
        verify_token_configured=bool(app_settings.WHATSAPP_VERIFY_TOKEN),
        app_secret_configured=bool(app_settings.WHATSAPP_APP_SECRET),
    )


@router.put("/whatsapp", response_model=ChannelOut)
async def connect_whatsapp(
    body: WhatsAppConnectIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChannelOut:
    _owner(user)
    taken = await session.scalar(
        select(ChannelConnection.tenant_id).where(
            ChannelConnection.channel == ChannelType.WHATSAPP.value,
            ChannelConnection.config["phone_number_id"].astext == body.phone_number_id,
            ChannelConnection.tenant_id != user.tenant_id,
        )
    )
    if taken is not None:
        raise AppError("phone_number_in_use", "This WhatsApp number is connected to another account.", 409)
    config: dict[str, Any] = {"phone_number_id": body.phone_number_id, "waba_id": body.waba_id}
    secrets = {"access_token": body.access_token}
    try:
        encrypted = encrypt_json(secrets)
    except CryptoError as exc:
        raise AppError("encryption_not_configured", str(exc), 500) from exc

    adapter = registry.build_channel(ChannelType.WHATSAPP, config, secrets)
    ok, detail = await adapter.check_connection()
    if ok:
        phone_details = getattr(adapter, "phone_details", None)  # optional extra on our adapters
        details: dict[str, Any] = await phone_details() if phone_details is not None else {}
        config["display_phone_number"] = details.get("display_phone_number") or detail
        for key in ("verified_name", "quality_rating"):
            if details.get(key):
                config[key] = details[key]

    row = await get_whatsapp_connection(session, user.tenant_id)
    if row is None:
        row = ChannelConnection(tenant_id=user.tenant_id, channel=ChannelType.WHATSAPP.value)
        session.add(row)
    row.config = config
    row.secrets_encrypted = encrypted
    row.status = "connected" if ok else "error"
    row.last_error = None if ok else detail
    row.last_checked_at = datetime.now(UTC)
    await session.flush()
    if ok:
        try:
            await sync_templates(session, user.tenant_id)
        except Exception as exc:  # templates can be synced later from the page
            row.last_error = f"connected, but templates could not be loaded: {exc}"[:500]
    await session.commit()
    return await _channel_out(session, user.tenant_id, row)


@router.post("/whatsapp/test", response_model=TestSendOut)
async def test_send(
    body: TestSendIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TestSendOut:
    _owner(user)
    to = normalize_eg_phone(body.to)
    if to is None:
        raise AppError("invalid_phone", "Enter an Egyptian mobile number, e.g. 010 1234 5678.", 400)
    settings = await get_settings_for(session, user.tenant_id)
    if settings.demo_mode and to not in (settings.demo_whitelist or []):
        raise AppError(
            "not_whitelisted",
            "Demo mode is on: add this number to the demo phones (Settings) before sending a test.",
            400,
        )
    try:
        adapter = await registry.get_channel(session, user.tenant_id, ChannelType.WHATSAPP)
    except registry.ChannelNotConnected as exc:
        raise AppError("channel_not_connected", "Connect WhatsApp first.", 400) from exc
    approved = [t for t in await _templates(session, user.tenant_id) if t.status == "approved"]
    template = next((t for t in approved if t.name == "hello_world"), None) or (
        approved[0] if approved else None
    )
    name = template.name if template else "hello_world"
    language = template.language if template else "en_US"
    params = ["تجربة"] * (template.param_count if template else 0)
    result = await adapter.send_template(to=to, template_name=name, language=language, params=params)
    return TestSendOut(
        ok=result.ok,
        to=to,
        template_name=name,
        provider_message_id=result.provider_message_id,
        error=result.error,
    )


@router.post("/whatsapp/templates/sync", response_model=TemplateList)
async def sync(
    user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> TemplateList:
    _owner(user)
    try:
        rows = await sync_templates(session, user.tenant_id)
    except registry.ChannelNotConnected as exc:
        raise AppError("channel_not_connected", "Connect WhatsApp first.", 400) from exc
    except Exception as exc:
        raise AppError("template_sync_failed", f"Could not load the templates from Meta: {exc}", 502) from exc
    await session.commit()
    return TemplateList(items=[_template_out(t) for t in rows], total=len(rows))


@router.put("/whatsapp/templates/{template_id}", response_model=TemplateOut)
async def tag_template(
    template_id: uuid.UUID,
    body: TemplatePurposeIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TemplateOut:
    _owner(user)
    row = (
        await session.execute(
            select(MessageTemplate).where(
                MessageTemplate.id == template_id, MessageTemplate.tenant_id == user.tenant_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("template")
    row.purpose = body.purpose
    await session.commit()
    return _template_out(row)
