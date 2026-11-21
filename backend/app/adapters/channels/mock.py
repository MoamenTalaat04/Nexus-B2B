"""In-memory WhatsApp channel for tests and development (USE_MOCK_ADAPTERS=true). Never sends anything.

- Every send is recorded in MockChannelAdapter.outbox (shared by all instances; tests clear it).
- `fail_next` makes the next send fail with that error code (e.g. "window_closed", "invalid_token").
- An access token equal to "invalid" fails check_connection, like a bad token would.
- simulate_inbound(...) / simulate_status(...) build the Meta-shaped webhook bodies for tests.
"""

import itertools
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

from app.adapters.base import SendResult, TemplateInfo
from app.adapters.channels.whatsapp_cloud import inbound_payload, sanitize_param, status_payload
from app.models.enums import ChannelType

MOCK_DISPLAY_NUMBER = "+20 100 000 0000"
MOCK_TEMPLATES = [
    TemplateInfo(
        name="hello_world",
        language="en_US",
        category="UTILITY",
        status="APPROVED",
        body_text="Hello World",
        param_count=0,
    ),
    TemplateInfo(
        name="intro",
        language="ar",
        category="MARKETING",
        status="APPROVED",
        body_text="أهلاً {{1}} 👋 معاك {{2}}. حابين نعرّفكم على تشكيلتنا الجديدة.",
        param_count=2,
    ),
    TemplateInfo(
        name="followup",
        language="ar",
        category="MARKETING",
        status="APPROVED",
        body_text="أهلاً تاني {{1}}، لسه مستنيين ردكم على التشكيلة الجديدة.",
        param_count=1,
    ),
]


@dataclass
class SentRecord:
    kind: str  # "template" | "text"
    to: str
    provider_message_id: str
    template_name: str | None = None
    language: str | None = None
    params: list[str] = field(default_factory=list)
    body: str | None = None


class MockChannelAdapter:
    channel = ChannelType.WHATSAPP
    outbox: ClassVar[list[SentRecord]] = []
    fail_next: ClassVar[str | None] = None
    _ids: ClassVar["itertools.count[int]"] = itertools.count(1)

    def __init__(self, *, phone_number_id: str = "mock-phone-id", access_token: str = "mock-token") -> None:
        self.phone_number_id = phone_number_id
        self._token = access_token

    @classmethod
    def reset(cls) -> None:
        cls.outbox.clear()
        cls.fail_next = None

    def _result(self) -> SendResult | None:
        if MockChannelAdapter.fail_next:
            error, MockChannelAdapter.fail_next = MockChannelAdapter.fail_next, None
            return SendResult(ok=False, error=error)
        return None

    @staticmethod
    def _new_id() -> str:
        return f"wamid.mock.{next(MockChannelAdapter._ids)}"

    async def send_template(
        self, *, to: str, template_name: str, language: str, params: list[str]
    ) -> SendResult:
        failed = self._result()
        if failed:
            return failed
        record = SentRecord(
            kind="template",
            to=to,
            provider_message_id=self._new_id(),
            template_name=template_name,
            language=language,
            params=[sanitize_param(p) for p in params],
        )
        MockChannelAdapter.outbox.append(record)
        return SendResult(ok=True, provider_message_id=record.provider_message_id)

    async def send_text(self, *, to: str, body: str) -> SendResult:
        failed = self._result()
        if failed:
            return failed
        record = SentRecord(kind="text", to=to, provider_message_id=self._new_id(), body=body)
        MockChannelAdapter.outbox.append(record)
        return SendResult(ok=True, provider_message_id=record.provider_message_id)

    async def check_connection(self) -> tuple[bool, str]:
        if self._token == "invalid":
            return False, "invalid_token: Error validating access token (code 190)"
        return True, MOCK_DISPLAY_NUMBER

    async def phone_details(self) -> dict[str, Any]:
        return {
            "display_phone_number": MOCK_DISPLAY_NUMBER,
            "verified_name": "Mock Business",
            "quality_rating": "GREEN",
        }

    async def list_templates(self) -> list[TemplateInfo]:
        return [t.model_copy() for t in MOCK_TEMPLATES]


MockChannel = MockChannelAdapter


def simulate_inbound(
    *,
    phone_number_id: str,
    from_phone: str,
    text: str,
    message_id: str | None = None,
    timestamp: datetime | None = None,
    kind: str = "text",
) -> dict[str, Any]:
    """The webhook body Meta would POST when `from_phone` sends `text` to our number."""
    return inbound_payload(
        phone_number_id=phone_number_id,
        from_phone=from_phone,
        text=text,
        message_id=message_id or f"wamid.in.{next(MockChannelAdapter._ids)}",
        timestamp=timestamp,
        kind=kind,
    )


def simulate_status(
    *, phone_number_id: str, message_id: str, status: str, error_code: int | None = None
) -> dict[str, Any]:
    return status_payload(
        phone_number_id=phone_number_id, message_id=message_id, status=status, error_code=error_code
    )
