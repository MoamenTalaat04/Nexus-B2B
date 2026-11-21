"""Business settings API schemas (P1-2, CONTRACTS section 3 business_settings, section 11 /settings).

SettingsOut is what GET/PUT return. SettingsUpdate is the PUT body: every field is optional and only the
fields present in the JSON are changed (partial update). Sending null is allowed only for nullable fields
(website).
"""

from datetime import time
from enum import StrEnum
from itertools import pairwise
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from app.core import geo_eg
from app.core.phones import normalize_eg_phone
from app.models.enums import AutonomyMode, FirstTouchMode, OutreachPurpose

MAX_PRODUCTS = 30
MAX_DEMO_WHITELIST = 5  # WhatsApp test numbers accept at most 5 recipient phones
SEND_CAP_WARNING_ABOVE = 50
NULLABLE_FIELDS = {"website"}


class ProductIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    price_range: str | None = Field(default=None, max_length=120)  # free text, e.g. "120-250 EGP / piece"
    min_order: str | None = Field(default=None, max_length=120)  # free text, e.g. "1 dozen per model"


class RegionIn(BaseModel):
    """A governorate from GET /settings/geo; cities empty = the whole governorate."""

    model_config = ConfigDict(str_strip_whitespace=True)

    governorate: str
    cities: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def _known_places(self) -> "RegionIn":
        info = geo_eg.get_governorate(self.governorate)
        if info is None:
            raise ValueError(f"unknown governorate {self.governorate!r}; use a name from GET /settings/geo")
        self.governorate = info.name
        cities: list[str] = []
        for city in self.cities:
            if not city:
                continue
            canonical = geo_eg.canonical_city(info, city) if info.cities else None
            if info.cities and canonical is None:
                raise ValueError(f"unknown city {city!r} in {info.name}; use a name from GET /settings/geo")
            name = canonical or city[:80]
            if name not in cities:
                cities.append(name)
        self.cities = cities
        return self


class SequenceStepIn(BaseModel):
    day_offset: int = Field(ge=0, le=60)
    purpose: Literal["first_touch", "followup"]
    template: str = Field(min_length=1, max_length=64)  # the template purpose tag: "intro" / "followup"


def _validate_sequence(steps: list[SequenceStepIn]) -> list[SequenceStepIn]:
    if not 1 <= len(steps) <= 4:
        raise ValueError("sequence_steps needs 1 to 4 steps")
    if steps[0].purpose != OutreachPurpose.FIRST_TOUCH.value:
        raise ValueError("the first step must be the first_touch")
    if any(s.purpose == OutreachPurpose.FIRST_TOUCH.value for s in steps[1:]):
        raise ValueError("only the first step can be a first_touch")
    offsets = [s.day_offset for s in steps]
    if any(b <= a for a, b in pairwise(offsets)):
        raise ValueError("day_offset must increase from step to step")
    return steps


def _normalize_whitelist(values: list[str]) -> list[str]:
    result: list[str] = []
    for raw in values:
        e164 = normalize_eg_phone(raw)
        if e164 is None:
            raise ValueError(f"{raw!r} is not a valid Egyptian phone number")
        if e164 not in result:
            result.append(e164)
    if len(result) > MAX_DEMO_WHITELIST:
        raise ValueError(f"at most {MAX_DEMO_WHITELIST} demo phones (the WhatsApp test-number limit)")
    return result


class SettingsUpdate(BaseModel):
    """PUT /api/v1/settings body. Only the fields you send are changed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_name: str | None = Field(default=None, max_length=200)
    website: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    ideal_customer_text: str | None = Field(default=None, max_length=5000)
    products: list[ProductIn] | None = Field(default=None, min_length=1, max_length=MAX_PRODUCTS)
    target_regions: list[RegionIn] | None = Field(default=None, min_length=1, max_length=27)
    language: Literal["ar-EG", "en"] | None = None
    tone: Literal["friendly", "formal"] | None = None
    allowed_offers: str | None = Field(default=None, max_length=2000)
    max_discount_percent: int | None = Field(default=None, ge=0, le=50)
    autonomy_mode: AutonomyMode | None = None
    first_touch_mode: FirstTouchMode | None = None
    agent_enabled: bool | None = None
    daily_new_leads_target: int | None = Field(default=None, ge=1, le=200)
    daily_send_cap: int | None = Field(default=None, ge=1, le=200)
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    working_days: list[int] | None = Field(default=None, min_length=1, max_length=7)
    score_threshold: int | None = Field(default=None, ge=1, le=10)
    sequence_steps: list[SequenceStepIn] | None = None
    demo_mode: bool | None = None
    demo_whitelist: list[str] | None = Field(default=None, max_length=20)
    onboarding_completed: bool | None = None

    @field_validator("website")
    @classmethod
    def _website(cls, value: str | None) -> str | None:
        if not value:
            return None
        if not value.lower().startswith(("http://", "https://")):
            value = "https://" + value
        return value

    @field_validator("working_days")
    @classmethod
    def _days(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(d < 0 or d > 6 for d in value):
            raise ValueError("working_days uses Mon=0 … Sun=6")
        return sorted(set(value))

    @field_validator("sequence_steps")
    @classmethod
    def _sequence(cls, value: list[SequenceStepIn] | None) -> list[SequenceStepIn] | None:
        return None if value is None else _validate_sequence(value)

    @field_validator("demo_whitelist")
    @classmethod
    def _whitelist(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _normalize_whitelist(value)

    @field_validator("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def _minutes(cls, value: time | None) -> time | None:
        return None if value is None else value.replace(second=0, microsecond=0, tzinfo=None)

    @model_validator(mode="after")
    def _no_null_for_required(self) -> "SettingsUpdate":
        for name in self.model_fields_set:
            if getattr(self, name) is None and name not in NULLABLE_FIELDS:
                raise ValueError(f"{name} cannot be null (leave it out to keep the current value)")
        return self

    def changes(self) -> dict[str, Any]:
        """The fields that were sent, as values ready for the ORM row (JSON columns as plain dicts)."""
        data: dict[str, Any] = {}
        for name in self.model_fields_set:
            value = getattr(self, name)
            if isinstance(value, list) and value and isinstance(value[0], BaseModel):
                value = [item.model_dump(mode="json") for item in value]
            elif isinstance(value, StrEnum):
                value = value.value
            data[name] = value
        return data


class SettingsOut(BaseModel):
    """GET/PUT /api/v1/settings response."""

    company_name: str
    website: str | None
    description: str
    ideal_customer_text: str
    products: list[dict[str, Any]]
    target_regions: list[dict[str, Any]]
    language: str
    tone: str
    allowed_offers: str
    max_discount_percent: int
    autonomy_mode: str
    first_touch_mode: str
    agent_enabled: bool
    daily_new_leads_target: int
    daily_send_cap: int
    quiet_hours_start: time
    quiet_hours_end: time
    working_days: list[int]
    score_threshold: int
    sequence_steps: list[dict[str, Any]]
    demo_mode: bool
    demo_whitelist: list[str]
    onboarding_completed: bool
    telegram_connected: bool
    warnings: list[str] = Field(default_factory=list)  # e.g. "daily_send_cap_above_50"

    @field_serializer("quiet_hours_start", "quiet_hours_end")
    def _hhmm(self, value: time) -> str:
        return value.strftime("%H:%M")


class CityOut(BaseModel):
    name: str
    name_ar: str


class GovernorateOut(BaseModel):
    name: str
    name_ar: str
    cities: list[CityOut]


class GeoOut(BaseModel):
    governorates: list[GovernorateOut]
