"""Where business code gets external-system adapters (CONTRACTS section 7). Never import a concrete adapter.

How to add an adapter: put the module next to its siblings (e.g. app/adapters/search/<name>.py) with a
class that implements the Protocol from app/adapters/base.py, then map its name in the matching getter
below. Real adapters are imported lazily, so a missing module only fails when it is actually used.

Stand-in written in P2-1 with only get_search_source. P3-2 (B) added get_channel / build_channel for the
WhatsApp channel. P0-1 owns this file and adds the mocks plus get_enrichers / get_notifier.
"""

import importlib
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import ChannelAdapter, SearchSource
from app.config import settings
from app.models.enums import ChannelType

# name → (module, class, the task that adds it)
_SEARCH_SOURCES = {
    "google_places": ("app.adapters.search.google_places", "GooglePlacesSource", "P2-1"),
}
_MOCK_SEARCH = ("app.adapters.search.mock", "MockSearchSource", "P0-1")


def _load(module_name: str, class_name: str, task: str) -> type:
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        raise NotImplementedError(f"{module_name} does not exist yet; it is added in {task}.") from exc
    cls: type = getattr(module, class_name)
    return cls


def get_search_source(name: str = "google_places") -> SearchSource:
    """The search source `name`, or the mock when USE_MOCK_ADAPTERS=true."""
    if settings.USE_MOCK_ADAPTERS:
        source: SearchSource = _load(*_MOCK_SEARCH)()
        return source
    if name not in _SEARCH_SOURCES:
        raise ValueError(f"Unknown search source {name!r}. Known: {', '.join(_SEARCH_SOURCES)}.")
    source = _load(*_SEARCH_SOURCES[name])()
    return source


# ------------------------------------------------------------------------------------ channels (P3-2)

_CHANNELS = {
    ChannelType.WHATSAPP: ("app.adapters.channels.whatsapp_cloud", "WhatsAppCloudAdapter", "P3-2"),
}
_MOCK_CHANNEL = ("app.adapters.channels.mock", "MockChannelAdapter", "P3-2")


class ChannelNotConnected(Exception):
    """The tenant has no working connection for this channel (Settings → Channels)."""

    def __init__(self, channel: ChannelType, reason: str = "not connected") -> None:
        super().__init__(f"{channel.value} is {reason}")
        self.channel = channel
        self.reason = reason


def build_channel(channel: ChannelType, config: dict[str, Any], secrets: dict[str, Any]) -> ChannelAdapter:
    """An adapter for explicit credentials (used to test them before saving), or the mock in mock mode."""
    if settings.USE_MOCK_ADAPTERS:
        mock: ChannelAdapter = _load(*_MOCK_CHANNEL)(
            phone_number_id=str(config.get("phone_number_id") or "mock-phone-id"),
            access_token=str(secrets.get("access_token") or "mock-token"),
        )
        return mock
    if channel not in _CHANNELS:
        raise ChannelNotConnected(channel, "not supported yet")
    adapter: ChannelAdapter = _load(*_CHANNELS[channel])(
        phone_number_id=str(config["phone_number_id"]),
        waba_id=str(config.get("waba_id") or ""),
        access_token=str(secrets["access_token"]),
    )
    return adapter


async def get_channel(session: AsyncSession, tenant_id: uuid.UUID, channel: ChannelType) -> ChannelAdapter:
    """The tenant's adapter for `channel` from channel_connections (secrets decrypted), or the mock.

    Raises ChannelNotConnected when there is no connected row (real mode only).
    """
    if settings.USE_MOCK_ADAPTERS:
        return build_channel(channel, {}, {})
    from app.core.crypto import decrypt_json  # local: keeps the registry importable without a key
    from app.models.messaging import ChannelConnection

    row = (
        await session.execute(
            select(ChannelConnection).where(
                ChannelConnection.tenant_id == tenant_id,
                ChannelConnection.channel == ChannelType(channel).value,
            )
        )
    ).scalar_one_or_none()
    if row is None or row.status != "connected" or not row.secrets_encrypted:
        raise ChannelNotConnected(ChannelType(channel))
    return build_channel(ChannelType(channel), dict(row.config or {}), decrypt_json(row.secrets_encrypted))
