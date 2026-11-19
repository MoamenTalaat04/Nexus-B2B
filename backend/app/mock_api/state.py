"""Deterministic in-memory data store for Mock API mode."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from typing import Any

from app.models.enums import (
    AutonomyMode,
    FirstTouchMode,
    LeadStatus,
)


@dataclass
class MockUser:
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    password: str
    full_name: str
    role: str = "owner"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockTenant:
    id: uuid.UUID
    name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockBusinessSettings:
    id: uuid.UUID
    tenant_id: uuid.UUID
    company_name: str = ""
    website: str | None = None
    description: str = ""
    ideal_customer_text: str = ""
    products: list[dict[str, Any]] = field(default_factory=list)
    target_regions: list[dict[str, Any]] = field(default_factory=list)
    language: str = "ar-EG"
    tone: str = "friendly"
    allowed_offers: str = ""
    max_discount_percent: int = 0
    autonomy_mode: str = AutonomyMode.APPROVE_ALL.value
    first_touch_mode: str = FirstTouchMode.ASSISTED.value
    agent_enabled: bool = False
    daily_new_leads_target: int = 30
    daily_send_cap: int = 20
    quiet_hours_start: time = field(default_factory=lambda: time(10, 0))
    quiet_hours_end: time = field(default_factory=lambda: time(20, 0))
    working_days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 5, 6])
    score_threshold: int = 6
    sequence_steps: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"day_offset": 0, "purpose": "first_touch", "template": "intro"},
            {"day_offset": 3, "purpose": "followup", "template": "followup"},
        ]
    )
    demo_mode: bool = True
    demo_whitelist: list[str] = field(default_factory=list)
    telegram_chat_id: str | None = None
    telegram_link_code: str | None = None
    onboarding_completed: bool = False
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockKnowledgeFile:
    id: uuid.UUID
    tenant_id: uuid.UUID
    filename: str
    mime_type: str
    size_bytes: int
    extracted_text: str
    char_count: int
    status: str = "ready"
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockIcpVersion:
    id: uuid.UUID
    tenant_id: uuid.UUID
    version: int
    company_profile: dict[str, Any]
    icp: dict[str, Any]
    source: str
    is_active: bool
    notes: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockAgentStep:
    id: uuid.UUID
    tenant_id: uuid.UUID
    run_id: uuid.UUID
    seq: int
    step_type: str
    name: str
    input: Any
    output: Any
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    lead_id: uuid.UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockAgentRun:
    id: uuid.UUID
    tenant_id: uuid.UUID
    kind: str
    status: str
    trigger: str
    input: dict[str, Any] = field(default_factory=dict)
    output_summary: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    poll_count: int = 0


@dataclass
class MockContact:
    id: uuid.UUID
    tenant_id: uuid.UUID
    lead_id: uuid.UUID
    type: str
    value: str
    source: str
    is_primary: bool = False
    confidence: float = 0.8
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockLeadStatusHistory:
    id: uuid.UUID
    tenant_id: uuid.UUID
    lead_id: uuid.UUID
    from_status: str
    to_status: str
    reason: str
    actor: str
    actor_user_id: uuid.UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockLeadNote:
    id: uuid.UUID
    tenant_id: uuid.UUID
    lead_id: uuid.UUID
    author_user_id: uuid.UUID
    body: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockLeadOutcome:
    id: uuid.UUID
    tenant_id: uuid.UUID
    lead_id: uuid.UUID
    outcome: str
    value_egp: float | None = None
    reason: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockLead:
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    source: str = "google_places"
    source_ref: str | None = None
    category: str | None = None
    address: str | None = None
    city: str | None = None
    governorate: str | None = None
    lat: float | None = None
    lng: float | None = None
    website: str | None = None
    domain: str | None = None
    google_maps_url: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    status: str = LeadStatus.NEW.value
    score: int | None = None
    score_reasons: list[str] = field(default_factory=list)
    disqualify_reason: str | None = None
    icp_version_id: uuid.UUID | None = None
    sourcing_run_id: uuid.UUID | None = None
    sequence_step: int = 0
    next_action_at: datetime | None = None
    agent_paused: bool = False
    first_contacted_at: datetime | None = None
    last_outbound_at: datetime | None = None
    last_inbound_at: datetime | None = None
    ref_code: str = "N3XUS1"
    dedupe_key: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockConversation:
    id: uuid.UUID
    tenant_id: uuid.UUID
    lead_id: uuid.UUID
    channel: str
    contact_value: str
    window_expires_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockMessage:
    id: uuid.UUID
    tenant_id: uuid.UUID
    conversation_id: uuid.UUID
    lead_id: uuid.UUID
    direction: str
    channel: str
    author: str
    kind: str
    body: str
    status: str
    purpose: str | None = None
    template_name: str | None = None
    template_params: list[str] | None = None
    provider_message_id: str | None = None
    error: str | None = None
    sent_at: datetime | None = None
    approved_by_user_id: uuid.UUID | None = None
    reply_intent: str | None = None
    redirected_to: str | None = None
    agent_run_id: uuid.UUID | None = None
    rationale: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockChannelConnection:
    id: uuid.UUID
    tenant_id: uuid.UUID
    channel: str
    status: str
    config: dict[str, Any] = field(default_factory=dict)
    last_checked_at: datetime | None = None
    last_error: str | None = None


@dataclass
class MockMessageTemplate:
    id: uuid.UUID
    tenant_id: uuid.UUID
    channel: str
    name: str
    language: str
    category: str
    purpose: str
    body_text: str
    param_count: int
    status: str = "approved"


@dataclass
class MockNotification:
    id: uuid.UUID
    tenant_id: uuid.UUID
    kind: str
    title: str
    body: str
    lead_id: uuid.UUID | None = None
    read_at: datetime | None = None
    telegram_sent_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockLearnedInsight:
    id: uuid.UUID
    tenant_id: uuid.UUID
    version: int
    insights: list[str]
    stats: dict[str, Any]
    is_active: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MockStore:
    """In-memory multi-tenant store."""

    def __init__(self) -> None:
        self.tenants: dict[uuid.UUID, MockTenant] = {}
        self.users: dict[uuid.UUID, MockUser] = {}
        self.settings: dict[uuid.UUID, MockBusinessSettings] = {}
        self.knowledge: dict[uuid.UUID, MockKnowledgeFile] = {}
        self.icp_versions: dict[uuid.UUID, MockIcpVersion] = {}
        self.runs: dict[uuid.UUID, MockAgentRun] = {}
        self.steps: dict[uuid.UUID, MockAgentStep] = {}
        self.leads: dict[uuid.UUID, MockLead] = {}
        self.contacts: dict[uuid.UUID, MockContact] = {}
        self.status_history: dict[uuid.UUID, MockLeadStatusHistory] = {}
        self.notes: dict[uuid.UUID, MockLeadNote] = {}
        self.outcomes: dict[uuid.UUID, MockLeadOutcome] = {}
        self.conversations: dict[uuid.UUID, MockConversation] = {}
        self.messages: dict[uuid.UUID, MockMessage] = {}
        self.channels: dict[uuid.UUID, MockChannelConnection] = {}
        self.templates: dict[uuid.UUID, MockMessageTemplate] = {}
        self.notifications: dict[uuid.UUID, MockNotification] = {}
        self.insights: dict[uuid.UUID, MockLearnedInsight] = {}
        self.sourcing_batch_counter: dict[uuid.UUID, int] = {}

    def clear(self) -> None:
        self.__init__()  # type: ignore[misc]


_store: MockStore | None = None


def get_store() -> MockStore:
    global _store
    if _store is None:
        _store = MockStore()
        from app.mock_api.seed import populate_seed_data

        populate_seed_data(_store)
    return _store


def reset_store() -> MockStore:
    global _store
    _store = MockStore()
    from app.mock_api.seed import populate_seed_data

    populate_seed_data(_store)
    return _store

