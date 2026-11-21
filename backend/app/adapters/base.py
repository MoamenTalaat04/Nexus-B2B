"""Adapter interfaces (CONTRACTS section 7, verbatim).

Business code depends on these Protocols and models only; concrete adapters come from app.adapters.registry.

Stand-in written in P2-1 (the Google Places adapter implements SearchSource) before P0-1 landed.
P0-1 owns this file; every model and Protocol from the contract is already here,
so P0-1 only adds docs and the mocks.
"""

import re
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ChannelType, ContactType, MessageStatus


class RegionFilter(BaseModel):
    governorate: str
    cities: list[str] = Field(default_factory=list)
    lat: float | None = None
    lng: float | None = None
    radius_m: int | None = None


class PlaceResult(BaseModel):
    source: str
    source_ref: str
    name: str
    category: str | None = None
    address: str | None = None
    city: str | None = None
    governorate: str | None = None
    lat: float | None = None
    lng: float | None = None
    phone_national: str | None = None
    phone_international: str | None = None
    website: str | None = None
    google_maps_url: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    business_status: str | None = None
    types: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class SearchSource(Protocol):
    name: str

    async def search(
        self, query: str, *, region: RegionFilter, max_results: int = 20
    ) -> list[PlaceResult]: ...


class ContactCandidate(BaseModel):
    type: ContactType
    value: str
    source: str
    confidence: float = 0.5


class Enricher(Protocol):
    name: str

    async def enrich(
        self, *, lead_name: str, website: str | None, known: list[ContactCandidate]
    ) -> list[ContactCandidate]: ...


class SendResult(BaseModel):
    ok: bool
    provider_message_id: str | None = None
    error: str | None = None


class TemplateInfo(BaseModel):
    name: str
    language: str
    category: str
    status: str
    body_text: str
    param_count: int


class InboundMessage(BaseModel):
    channel: ChannelType
    account_ref: str  # WhatsApp phone_number_id that received it
    from_phone: str
    provider_message_id: str
    text: str
    timestamp: datetime
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("from_phone")
    @classmethod
    def validate_from_phone(cls, value: str) -> str:
        if re.fullmatch(r"\+[1-9]\d{1,14}", value) is None:
            raise ValueError("from_phone must be in E.164 format")
        return value


class StatusUpdate(BaseModel):
    provider_message_id: str
    status: MessageStatus
    error: str | None = None
    timestamp: datetime


class ChannelAdapter(Protocol):
    channel: ChannelType

    async def send_template(
        self, *, to: str, template_name: str, language: str, params: list[str]
    ) -> SendResult: ...

    async def send_text(self, *, to: str, body: str) -> SendResult: ...

    async def check_connection(self) -> tuple[bool, str]: ...

    async def list_templates(self) -> list[TemplateInfo]: ...


class Notifier(Protocol):
    async def notify(self, *, chat_id: str, text: str) -> bool: ...
