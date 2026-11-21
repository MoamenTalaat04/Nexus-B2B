import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.adapters import registry
from app.adapters.base import InboundMessage, RegionFilter
from app.adapters.channels.mock import MockChannel, MockChannelAdapter, simulate_inbound, simulate_status
from app.adapters.enrichment.mock import MockEnricher
from app.adapters.notify.mock import MockNotifier
from app.adapters.search.mock import MockSearchSource
from app.models.enums import ChannelType


async def test_mock_search_is_deterministic_and_contains_believable_data() -> None:
    source = MockSearchSource()
    region = RegionFilter(governorate="Cairo", cities=["Nasr City"])

    first = await source.search("kids clothing shop", region=region, max_results=12)
    second = await source.search("kids clothing shop", region=region, max_results=12)

    assert first == second
    assert len(first) == 12
    assert all(place.governorate == "Cairo" for place in first)
    assert all(place.city == "Nasr City" for place in first)
    assert any(place.phone_international and place.phone_international.startswith("+20") for place in first)


async def test_mock_search_respects_region_and_limit() -> None:
    source = MockSearchSource()
    results = await source.search(
        "pharmacy",
        region=RegionFilter(governorate="Giza", cities=["Dokki"]),
        max_results=7,
    )
    assert len(results) == 7
    assert all(result.governorate == "Giza" and result.city == "Dokki" for result in results)
    assert await source.search("pharmacy", region=RegionFilter(governorate="Giza"), max_results=0) == []


def test_mock_search_source_is_valid_utf8_and_arabic_output() -> None:
    source_path = Path(__file__).parents[1] / "app" / "adapters" / "search" / "mock.py"
    source_path.read_bytes().decode("utf-8", errors="strict")
    assert "\ufffd" not in source_path.read_text(encoding="utf-8")

    import asyncio

    results = asyncio.run(
        MockSearchSource().search(
            "ملابس أطفال",
            region=RegionFilter(governorate="Cairo", cities=["Nasr City"]),
            max_results=4,
        )
    )
    assert any("ملابس" in place.name for place in results)
    assert any("أطفال" in place.name for place in results)


async def test_mock_enricher_is_deterministic() -> None:
    enricher = MockEnricher()
    first = await enricher.enrich(lead_name="Little Stars Kids Wear", website=None, known=[])
    second = await enricher.enrich(lead_name="Little Stars Kids Wear", website=None, known=[])
    assert first == second
    assert all(candidate.value.startswith("+20") for candidate in first)


async def test_mock_notifier_records_notifications() -> None:
    MockNotifier.reset()
    notifier = MockNotifier()
    assert await notifier.notify(chat_id="123", text="Hot lead")
    assert MockNotifier.notifications[-1].chat_id == "123"
    assert MockNotifier.notifications[-1].text == "Hot lead"


async def test_mock_channel_send_inbound_and_status_round_trip() -> None:
    MockChannelAdapter.reset()
    channel = MockChannelAdapter(phone_number_id="mock-phone-id")

    template = await channel.send_template(
        to="+201000000001",
        template_name="intro",
        language="ar",
        params=["Stars", "Nexus"],
    )
    text = await channel.send_text(to="+201000000001", body="مرحبا")

    assert template.ok and template.provider_message_id
    assert text.ok and text.provider_message_id
    assert [record.kind for record in MockChannelAdapter.outbox] == ["template", "text"]

    inbound_payload = simulate_inbound(
        phone_number_id="mock-phone-id",
        from_phone="+201000000001",
        text="Interested",
    )
    status_payload = simulate_status(
        phone_number_id="mock-phone-id",
        message_id=template.provider_message_id or "",
        status="sent",
    )
    assert inbound_payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"] == "Interested"
    assert status_payload["entry"][0]["changes"][0]["value"]["statuses"][0]["status"] == "sent"


def test_mock_channel_name_is_backward_compatible_alias() -> None:
    assert MockChannel is MockChannelAdapter


def test_registry_returns_mocks_in_mock_mode() -> None:
    assert registry.settings.USE_MOCK_ADAPTERS is True
    assert isinstance(registry.get_search_source(), MockSearchSource)
    assert all(isinstance(item, MockEnricher) for item in registry.get_enrichers())
    assert isinstance(registry.get_notifier(), MockNotifier)


def test_registry_real_mode_names_missing_tasks() -> None:
    with patch.object(registry.settings, "USE_MOCK_ADAPTERS", False):
        names = sorted(type(item).__name__ for item in registry.get_enrichers())  # P3-1 landed
        assert names == ["PlacesContactsEnricher", "WebsiteCrawlerEnricher"]
        with pytest.raises(NotImplementedError, match=r"app\.adapters\.notify\.telegram.*P4-2"):
            registry.get_notifier()


def test_registry_real_search_missing_module_is_clear() -> None:
    with pytest.raises(NotImplementedError, match=r"app\.adapters\.search\.missing.*P9-9"):
        registry._load("app.adapters.search.missing", "Missing", "P9-9")


def test_inbound_message_rejects_non_e164_phone() -> None:
    with pytest.raises(ValidationError):
        InboundMessage(
            channel=ChannelType.WHATSAPP,
            account_ref="mock-phone-id",
            from_phone="01000000001",
            provider_message_id="wamid.mock",
            text="مرحبا",
            timestamp=datetime.now(UTC),
        )


@pytest.mark.parametrize(
    "phone",
    [
        "+201012345678",
        "+12345678901234",
        "+123456789012345",
    ],
)
def test_inbound_message_accepts_generic_e164(phone: str) -> None:
    message = InboundMessage(
        channel=ChannelType.WHATSAPP,
        account_ref="mock-phone-id",
        from_phone=phone,
        provider_message_id="wamid.mock",
        text="مرحبا",
        timestamp=datetime.now(UTC),
    )
    assert message.from_phone == phone


@pytest.mark.parametrize(
    "phone",
    [
        "01000000001",
        "+012345678",
        "++201012345678",
        "+20101234567890123",
        "+",
    ],
)
def test_inbound_message_rejects_invalid_e164(phone: str) -> None:
    with pytest.raises(ValidationError):
        InboundMessage(
            channel=ChannelType.WHATSAPP,
            account_ref="mock-phone-id",
            from_phone=phone,
            provider_message_id="wamid.mock",
            text="مرحبا",
            timestamp=datetime.now(UTC),
        )


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self.value = value

    def scalar_one_or_none(self) -> Any:
        return self.value


class _ChannelSession:
    def __init__(self, row: Any) -> None:
        self.row = row
        self.executed = False

    async def execute(self, _: Any) -> _ScalarResult:
        self.executed = True
        return _ScalarResult(self.row)


@pytest.mark.asyncio
async def test_get_channel_mock_mode_never_looks_up_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _ChannelSession(SimpleNamespace(status="disconnected"))
    monkeypatch.setattr(registry.settings, "USE_MOCK_ADAPTERS", True)

    channel = await registry.get_channel(session, uuid.uuid4(), ChannelType.WHATSAPP)

    assert isinstance(channel, MockChannelAdapter)
    assert session.executed is False


@pytest.mark.asyncio
async def test_get_channel_returns_connected_tenant_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    row = SimpleNamespace(
        tenant_id=tenant_id,
        status="connected",
        secrets_encrypted="encrypted",
        config={"phone_number_id": "tenant-phone", "waba_id": "tenant-waba"},
    )
    session = _ChannelSession(row)
    marker = object()
    monkeypatch.setattr(registry.settings, "USE_MOCK_ADAPTERS", False)
    monkeypatch.setattr("app.core.crypto.decrypt_json", lambda _: {"access_token": "tenant-token"})
    monkeypatch.setattr(
        registry,
        "build_channel",
        lambda channel, config, secrets: marker,
    )

    result = await registry.get_channel(session, tenant_id, ChannelType.WHATSAPP)

    assert result is marker
    assert session.executed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "row",
    [
        None,
        SimpleNamespace(status="disconnected", secrets_encrypted="encrypted", config={}),
        SimpleNamespace(status="connected", secrets_encrypted=None, config={}),
    ],
)
async def test_get_channel_connection_errors(
    monkeypatch: pytest.MonkeyPatch,
    row: Any,
) -> None:
    monkeypatch.setattr(registry.settings, "USE_MOCK_ADAPTERS", False)
    session = _ChannelSession(row)

    with pytest.raises(registry.ChannelNotConnected):
        await registry.get_channel(session, uuid.uuid4(), ChannelType.WHATSAPP)


def test_mock_channel_registry_label_is_p0_1() -> None:
    assert registry._MOCK_CHANNEL == (
        "app.adapters.channels.mock",
        "MockChannel",
        "P0-1",
    )


def test_missing_real_channel_adapter_error_names_p3_2() -> None:
    with pytest.raises(NotImplementedError, match=r"app\.adapters\.channels\.missing.*P3-2"):
        registry._load("app.adapters.channels.missing", "MissingChannelAdapter", "P3-2")
