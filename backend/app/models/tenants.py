"""Tenants and their business settings (CONTRACTS section 3).

Stand-in written in P0-3/P1-3, before P0-2 landed: `tenants` (needed by the run tables) and
`business_settings` (needed by the ICP builder), column by column from the contract.
P0-2 owns this file and added `users` (migration 0006).
"""

import uuid
from datetime import time
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Text, Time, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import AutonomyMode, FirstTouchMode, enum_check

DEFAULT_SEQUENCE_STEPS_SQL = (
    '\'[{"day_offset": 0, "purpose": "first_touch", "template": "intro"}, '
    '{"day_offset": 3, "purpose": "followup", "template": "followup"}]\'::jsonb'
)


class Tenant(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(Text, nullable=False)


USER_ROLES = ("owner", "member")


class User(UUIDPkMixin, TimestampMixin, TenantMixin, Base):
    """A login. `email` is globally unique and always stored lowercase; `password_hash` is argon2 (P0-4)."""

    __tablename__ = "users"
    __table_args__ = (
        enum_check("role", USER_ROLES),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="owner")


class BusinessSettings(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "business_settings"
    __table_args__ = (
        enum_check("language", ("ar-EG", "en")),
        enum_check("tone", ("friendly", "formal")),
        enum_check("autonomy_mode", AutonomyMode),
        enum_check("first_touch_mode", FirstTouchMode),
    )

    # One row per tenant, so a unique tenant_id instead of the TenantMixin's plain index.
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    company_name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    ideal_customer_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # [{name, description, price_range, min_order}]
    products: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # [{governorate, cities: [...]}]
    target_regions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default="ar-EG")
    tone: Mapped[str] = mapped_column(Text, nullable=False, server_default="friendly")
    allowed_offers: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    max_discount_percent: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    autonomy_mode: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=AutonomyMode.APPROVE_ALL.value
    )
    first_touch_mode: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=FirstTouchMode.ASSISTED.value
    )
    agent_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    daily_new_leads_target: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")
    daily_send_cap: Mapped[int] = mapped_column(Integer, nullable=False, server_default="20")
    quiet_hours_start: Mapped[time] = mapped_column(Time, nullable=False, server_default=text("'10:00'"))
    quiet_hours_end: Mapped[time] = mapped_column(Time, nullable=False, server_default=text("'20:00'"))
    # Python weekday() numbering, Mon=0 ... Sun=6; default Saturday-Thursday
    working_days: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False, server_default=text("'{0,1,2,3,5,6}'")
    )
    score_threshold: Mapped[int] = mapped_column(Integer, nullable=False, server_default="6")
    sequence_steps: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text(DEFAULT_SEQUENCE_STEPS_SQL)
    )
    demo_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    demo_whitelist: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    telegram_chat_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_link_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
