# CONTRACTS — source of truth

> Every task builds against this file. To change it: a separate PR labeled `contract`, approved by 2+ members, announced in the group.
> Names here (tables, columns, enums, functions, routes) must be used **exactly**.

## 1. Conventions
- All tables: `id UUID PK default gen_random_uuid()`, `created_at timestamptz default now()`, `updated_at timestamptz` (auto-updated).
- Tenant-scoped tables have `tenant_id UUID NOT NULL FK tenants(id)` + an index on it.
- Enums are stored as Postgres `text` with a CHECK constraint (easier migrations) and mirrored as Python `StrEnum` in `app/models/enums.py` and TS union types in `frontend/src/lib/types.ts`.
- Phone numbers are stored in **E.164** (`+201012345678`).
- Money: `numeric(12,6)` USD for LLM cost; `numeric(14,2)` EGP for deal value.
- Times: UTC in the DB; business rules (quiet hours, cron) use `Africa/Cairo`.
- API: JSON, under `/api/v1`. Errors: `{"error": {"code": "snake_case", "message": "..."}}`. Lists: `?page=1&page_size=25` → `{"items": [...], "total": n}`.
- Errors are raised as `AppError(code, message, status_code)` from `app/core/errors.py` (scaffold); the global handler renders the shape above. Unknown routes, validation errors and crashes use the same shape (`not_found`, `validation_error`, `internal_error`).
- Routers: any `app/api/<area>.py` exposing `router` is auto-mounted under `/api/v1`. Jobs: any `async def job_*` in `app/workers/jobs/*.py` is auto-registered; cron jobs go in a module-level `CRON_JOBS` list.
- Auth: JWT in an httpOnly cookie `access_token`. The FastAPI dependency `get_current_user` returns `CurrentUser(user_id, tenant_id, role)`.

## 2. Enums (`app/models/enums.py`)

```python
class LeadStatus(StrEnum):
    NEW = "new"; QUALIFIED = "qualified"; DISQUALIFIED = "disqualified"
    ENRICHED = "enriched"; NO_CONTACT = "no_contact"; QUEUED = "queued"
    CONTACTED = "contacted"; REPLIED = "replied"
    INTERESTED = "interested"; NOT_INTERESTED = "not_interested"
    WANTS_OFFER = "wants_offer"; WANTS_MANAGEMENT = "wants_management"
    LATER = "later"; WRONG_CONTACT = "wrong_contact"; OPTED_OUT = "opted_out"
    WON = "won"; LOST = "lost"

class ReplyIntent(StrEnum):
    INTERESTED = "interested"; NOT_INTERESTED = "not_interested"
    WANTS_OFFER = "wants_offer"; WANTS_MANAGEMENT = "wants_management"
    LATER = "later"; WRONG_CONTACT = "wrong_contact"; OPTED_OUT = "opted_out"
    QUESTION = "question"; OTHER = "other"

class AutonomyMode(StrEnum):
    APPROVE_ALL = "approve_all"; APPROVE_FIRST_TOUCH = "approve_first_touch"; AUTOPILOT = "autopilot"

class AgentRunKind(StrEnum):
    ICP_BUILD = "icp_build"; SOURCING = "sourcing"; SCORING = "scoring"
    ENRICHMENT = "enrichment"; OUTREACH_TICK = "outreach_tick"; REPLY = "reply"; FEEDBACK = "feedback"

class AgentRunStatus(StrEnum):
    QUEUED = "queued"; RUNNING = "running"; SUCCEEDED = "succeeded"; FAILED = "failed"; CANCELLED = "cancelled"

class StepType(StrEnum):
    LLM_CALL = "llm_call"; TOOL_CALL = "tool_call"; EXTERNAL_API = "external_api"; DECISION = "decision"; ERROR = "error"

class ChannelType(StrEnum): WHATSAPP = "whatsapp"; TELEGRAM = "telegram"; EMAIL = "email"
class ContactType(StrEnum):
    MOBILE = "mobile"; LANDLINE = "landline"; EMAIL = "email"; WHATSAPP_LINK = "whatsapp_link"
    FACEBOOK = "facebook"; INSTAGRAM = "instagram"; WEBSITE = "website"
class MessageDirection(StrEnum): OUTBOUND = "outbound"; INBOUND = "inbound"
class MessageAuthor(StrEnum): AGENT = "agent"; HUMAN = "human"; LEAD = "lead"
class MessageKind(StrEnum): TEMPLATE = "template"; TEXT = "text"
class MessageStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"; APPROVED = "approved"; REJECTED = "rejected"
    QUEUED = "queued"; SENT = "sent"; DELIVERED = "delivered"; READ = "read"
    FAILED = "failed"; RECEIVED = "received"; BLOCKED = "blocked"   # blocked = refused by a guardrail (opt-out, cap)
class OutreachPurpose(StrEnum): FIRST_TOUCH = "first_touch"; FOLLOWUP = "followup"; REPLY = "reply"
```

Intent → status mapping (used by the reply pipeline):
`interested→interested, not_interested→not_interested, wants_offer→wants_offer, wants_management→wants_management, later→later, wrong_contact→wrong_contact, opted_out→opted_out, question→replied, other→replied`.

## 3. Tables

| Table | Columns (besides id/created_at/updated_at) | Owner task |
|---|---|---|
| `tenants` | `name` | P0-2 |
| `users` | `tenant_id`, `email` (unique, lowercase), `password_hash` (argon2), `full_name`, `role` ('owner'\|'member') | P0-2 |
| `business_settings` | `tenant_id` (unique), `company_name`, `website`, `description`, `ideal_customer_text text` (owner's own words about who they sell to), `products jsonb` (list of {name, description, price_range, min_order}), `target_regions jsonb` (list of {governorate, cities[]}), `language` ('ar-EG'\|'en'), `tone` ('friendly'\|'formal'), `allowed_offers text`, `max_discount_percent int default 0`, `autonomy_mode default 'approve_all'`, `agent_enabled bool default false`, `daily_new_leads_target int default 30`, `daily_send_cap int default 20`, `quiet_hours_start time default '10:00'`, `quiet_hours_end time default '20:00'`, `working_days int[] default {0,1,2,3,5,6}` (Mon=0 … Sun=6; default Sat–Thu), `score_threshold int default 6`, `sequence_steps jsonb default [{"day_offset":0,"purpose":"first_touch","template":"intro"},{"day_offset":3,"purpose":"followup","template":"followup"}]`, `demo_mode bool default true`, `demo_whitelist jsonb default []` (E.164 list), `telegram_chat_id text null`, `telegram_link_code text null`, `onboarding_completed bool default false` | P0-2 (cols), P1-2 (API/UI) |
| `knowledge_files` | `tenant_id`, `filename`, `mime_type`, `size_bytes`, `storage_path`, `extracted_text text`, `char_count int`, `status` ('processing'\|'ready'\|'failed'), `error text` | P0-2, P1-1 |
| `icp_versions` | `tenant_id`, `version int`, `company_profile jsonb` (CompanyProfile), `icp jsonb` (ICP), `source` ('agent'\|'user'), `is_active bool`, `notes text`; unique(tenant_id, version) | P0-2, P1-3 |
| `agent_runs` | `tenant_id`, `kind` AgentRunKind, `status` AgentRunStatus, `trigger` ('manual'\|'schedule'\|'webhook'\|'chained'), `input jsonb`, `output_summary jsonb`, `error text`, `started_at`, `finished_at`, `total_input_tokens int`, `total_output_tokens int`, `total_cost_usd numeric(12,6)` | P0-2, P0-3 |
| `agent_steps` | `tenant_id`, `run_id` FK, `seq int`, `step_type` StepType, `name text`, `input jsonb`, `output jsonb`, `model text null`, `input_tokens int`, `output_tokens int`, `cache_read_tokens int`, `cost_usd numeric(12,6)`, `latency_ms int`, `lead_id uuid null` | P0-2, P0-3 |
| `search_queries` | `tenant_id`, `run_id`, `source text`, `query_text`, `region jsonb`, `results_count int` | P0-2, P2-1 |
| `leads` | `tenant_id`, `source text`, `source_ref text` (e.g. place_id), `name`, `category text`, `address`, `city`, `governorate`, `lat float`, `lng float`, `website`, `domain`, `google_maps_url`, `rating float`, `reviews_count int`, `raw jsonb`, `status` LeadStatus default 'new', `score int null`, `score_reasons jsonb` (list[str]), `disqualify_reason text`, `icp_version_id uuid null`, `sourcing_run_id uuid null`, `sequence_step int default 0`, `next_action_at timestamptz null`, `agent_paused bool default false`, `first_contacted_at`, `last_outbound_at`, `last_inbound_at`, `dedupe_key text`; unique(tenant_id, dedupe_key) | P0-2 |
| `contacts` | `tenant_id`, `lead_id`, `type` ContactType, `value` (normalized), `source` ('google_places'\|'website'\|'manual'), `is_primary bool`, `confidence float`; unique(tenant_id, lead_id, type, value) | P0-2 |
| `channel_connections` | `tenant_id`, `channel` ChannelType, `status` ('connected'\|'error'\|'disconnected'), `config jsonb` (non-secret: phone_number_id, waba_id, display_phone_number), `secrets_encrypted text` (Fernet JSON), `last_checked_at`, `last_error`; unique(tenant_id, channel) | P0-2, P3-2 |
| `message_templates` | `tenant_id`, `channel`, `name` (Meta template name), `language` ('ar'), `category`, `purpose` ('intro'\|'followup'), `body_text`, `param_count int`, `status` ('approved'\|'pending'\|'rejected') | P0-2, P3-2 |
| `conversations` | `tenant_id`, `lead_id`, `channel`, `contact_value` (E.164 of the lead), `window_expires_at timestamptz null` (24h customer-service window) ; unique(tenant_id, lead_id, channel) | P0-2, P3-2 |
| `messages` | `tenant_id`, `conversation_id`, `lead_id`, `direction`, `channel`, `author` MessageAuthor, `kind` MessageKind, `purpose` OutreachPurpose null, `template_name null`, `template_params jsonb null`, `body text` (rendered text for display), `status` MessageStatus, `provider_message_id text unique null`, `error text`, `sent_at`, `approved_by_user_id null`, `reply_intent` ReplyIntent null (inbound only), `redirected_to text null` (demo), `agent_run_id null` | P0-2 |
| `demo_routes` | `tenant_id`, `test_phone` (E.164), `lead_id`; unique(tenant_id, test_phone) | P0-2, P3-2 |
| `lead_status_history` | `tenant_id`, `lead_id`, `from_status`, `to_status`, `reason text`, `actor` ('agent'\|'user'\|'system'), `actor_user_id null` | P0-2 |
| `lead_notes` | `tenant_id`, `lead_id`, `author_user_id`, `body` | P0-2 |
| `lead_outcomes` | `tenant_id`, `lead_id`, `outcome` ('won'\|'lost'), `value_egp numeric(14,2) null`, `reason text` | P0-2 |
| `notifications` | `tenant_id`, `lead_id null`, `kind` ('hot_lead'\|'wants_management'\|'wants_offer'\|'needs_approval'\|'channel_error'\|'run_failed'), `title`, `body`, `read_at null`, `telegram_sent_at null` | P0-2 |
| `learned_insights` | `tenant_id`, `version int`, `insights jsonb` (list[str]), `stats jsonb`, `is_active bool` | P0-2, P4-4 |

Note on `working_days`: Python `datetime.weekday()` numbering (Mon=0 … Sun=6). The default is Saturday–Thursday (Egyptian shops are usually closed or slow on Friday morning). The owner can change it.

## 4. Lead state machine (`app/core/lead_state.py`)

```python
ALLOWED: dict[LeadStatus, set[LeadStatus]] = {
  NEW: {QUALIFIED, DISQUALIFIED},
  QUALIFIED: {ENRICHED, NO_CONTACT, DISQUALIFIED},
  NO_CONTACT: {ENRICHED},                      # e.g. manual contact added
  ENRICHED: {QUEUED},
  QUEUED: {CONTACTED, ENRICHED},               # back to ENRICHED if the first message is rejected
  CONTACTED: {REPLIED, WON, LOST},
  REPLIED: {INTERESTED, NOT_INTERESTED, WANTS_OFFER, WANTS_MANAGEMENT, LATER, WRONG_CONTACT, WON, LOST},
  INTERESTED: {WANTS_OFFER, WANTS_MANAGEMENT, LATER, NOT_INTERESTED, WON, LOST, REPLIED},
  WANTS_OFFER: {INTERESTED, WANTS_MANAGEMENT, LATER, NOT_INTERESTED, WON, LOST, REPLIED},
  WANTS_MANAGEMENT: {INTERESTED, WANTS_OFFER, LATER, NOT_INTERESTED, WON, LOST, REPLIED},
  LATER: {CONTACTED, REPLIED, INTERESTED, NOT_INTERESTED, WON, LOST},
  NOT_INTERESTED: {REPLIED, LOST},
  WRONG_CONTACT: {ENRICHED, LOST},
  WON: set(), LOST: {REPLIED}, OPTED_OUT: set(),
}
# Any non-terminal status may go to OPTED_OUT. Classified statuses may go back to REPLIED on a new inbound message.

async def transition(session, lead: Lead, to: LeadStatus, *, reason: str, actor: Literal["agent","user","system"],
                     actor_user_id: UUID | None = None, force: bool = False) -> None
    # raises InvalidTransition unless allowed (force=True only for actor="user"); writes lead_status_history.
```

## 5. Core helpers (signatures are fixed)

```python
# app/core/tracing.py
class RunContext:
    run_id: UUID; tenant_id: UUID; kind: AgentRunKind
    async def step(self, step_type: StepType, name: str, *, input: Any = None, output: Any = None,
                   model: str | None = None, input_tokens: int = 0, output_tokens: int = 0,
                   cache_read_tokens: int = 0, cost_usd: float = 0.0, latency_ms: int = 0,
                   lead_id: UUID | None = None) -> None
@asynccontextmanager
async def agent_run(tenant_id: UUID, kind: AgentRunKind, *, trigger: str, input: dict,
                    run_id: UUID | None = None) -> AsyncIterator[RunContext]
    # opens its own DB session for trace rows; marks succeeded/failed; aggregates tokens and cost on exit.
    # If run_id is given (a row pre-created with status=queued by an API endpoint), that row is reused.
async def create_queued_run(session, tenant_id: UUID, kind: AgentRunKind, *, trigger: str, input: dict) -> UUID

# app/core/crypto.py
def encrypt_json(data: dict) -> str; def decrypt_json(token: str) -> dict

# app/core/phones.py   (P2-2)
def normalize_eg_phone(raw: str) -> str | None        # → E.164 or None
def is_eg_mobile(e164: str) -> bool                    # +20 10/11/12/15 + 8 digits

# app/core/tenancy.py
async def get_settings_for(session, tenant_id) -> BusinessSettings
```

## 6. LLM layer (`app/agents/llm.py`, P0-3)

```python
class ModelTier(StrEnum): SMART = "smart"; FAST = "fast"   # → settings.MODEL_SMART / MODEL_FAST
Effort = Literal["low", "medium", "high"]

async def llm_structured(run: RunContext, *, name: str, tier: ModelTier, system: str,
                         user: str, output_model: type[T], cached_context: str | None = None,
                         effort: Effort = "medium", max_tokens: int = 8000,
                         lead_id: UUID | None = None) -> T
    # system + cached_context form a cached prefix; user is the volatile part.
    # Uses structured outputs; checks stop_reason; retries rate-limit/5xx; records one agent_step.

@dataclass
class ToolSpec:
    name: str; description: str; input_model: type[BaseModel]
    handler: Callable[[BaseModel], Awaitable[dict]]   # bound server-side to tenant+lead

@dataclass
class ToolLoopResult:
    final_text: str; tool_calls: list[dict]; iterations: int; stopped_reason: str

async def llm_tool_loop(run: RunContext, *, name: str, tier: ModelTier, system: str,
                        messages: list[dict], tools: list[ToolSpec], cached_context: str | None = None,
                        effort: Effort = "medium", max_iterations: int = 6,
                        lead_id: UUID | None = None) -> ToolLoopResult
    # tool_choice=auto, strict tools; records an llm_call step per model turn and a tool_call step per tool.

class LLMRefused(Exception): ...
class LLMOutputTruncated(Exception): ...
```
When `USE_MOCK_LLM=true`: `llm_structured` returns a deterministic instance built from `output_model` (polyfactory, seeded by `name`) unless a fixture exists at `backend/tests/fixtures/llm/<name>.json`. `llm_tool_loop` returns a fixed result with no tool calls.

Cost is computed from the token usage with a price table in `app/agents/pricing.py` (USD per 1M tokens: input, output, cache read), keyed by model id.

## 7. Adapter interfaces (`app/adapters/base.py`, P0-1)

```python
class RegionFilter(BaseModel):
    governorate: str; cities: list[str] = []; lat: float | None = None; lng: float | None = None; radius_m: int | None = None

class PlaceResult(BaseModel):
    source: str; source_ref: str; name: str; category: str | None = None
    address: str | None = None; city: str | None = None; governorate: str | None = None
    lat: float | None = None; lng: float | None = None
    phone_national: str | None = None; phone_international: str | None = None
    website: str | None = None; google_maps_url: str | None = None
    rating: float | None = None; reviews_count: int | None = None
    business_status: str | None = None; types: list[str] = []; raw: dict = {}

class SearchSource(Protocol):
    name: str
    async def search(self, query: str, *, region: RegionFilter, max_results: int = 20) -> list[PlaceResult]: ...

class ContactCandidate(BaseModel):
    type: ContactType; value: str; source: str; confidence: float = 0.5

class Enricher(Protocol):
    name: str
    async def enrich(self, *, lead_name: str, website: str | None, known: list[ContactCandidate]) -> list[ContactCandidate]: ...

class SendResult(BaseModel):
    ok: bool; provider_message_id: str | None = None; error: str | None = None

class TemplateInfo(BaseModel):
    name: str; language: str; category: str; status: str; body_text: str; param_count: int

class InboundMessage(BaseModel):
    channel: ChannelType; account_ref: str   # WhatsApp phone_number_id that received it
    from_phone: str; provider_message_id: str; text: str; timestamp: datetime; raw: dict = {}

class StatusUpdate(BaseModel):
    provider_message_id: str; status: MessageStatus; error: str | None = None; timestamp: datetime

class ChannelAdapter(Protocol):
    channel: ChannelType
    async def send_template(self, *, to: str, template_name: str, language: str, params: list[str]) -> SendResult: ...
    async def send_text(self, *, to: str, body: str) -> SendResult: ...
    async def check_connection(self) -> tuple[bool, str]: ...
    async def list_templates(self) -> list[TemplateInfo]: ...

class Notifier(Protocol):
    async def notify(self, *, chat_id: str, text: str) -> bool: ...
```

`app/adapters/registry.py`:
```python
def get_search_source(name: str = "google_places") -> SearchSource
def get_enrichers() -> list[Enricher]
async def get_channel(session, tenant_id: UUID, channel: ChannelType) -> ChannelAdapter   # raises ChannelNotConnected
def get_notifier() -> Notifier
```
All of them return mocks when `USE_MOCK_ADAPTERS=true`. The mock channel records sent messages in memory and exposes `simulate_inbound(...)` for tests.

## 8. Domain schemas (`app/schemas/agent_io.py`)

```python
class Product(BaseModel): name: str; description: str = ""; price_range: str | None = None; min_order: str | None = None
class FAQ(BaseModel): q: str; a: str
class CompanyProfile(BaseModel):
    company_name: str; one_liner: str; products: list[Product]; differentiators: list[str]
    target_customer_summary: str; allowed_offers: str = ""; max_discount_percent: int = 0
    faqs: list[FAQ] = []; tone: str = "friendly"; language: str = "ar-EG"

class RegionTarget(BaseModel): governorate: str; cities: list[str] = []
class ICP(BaseModel):
    summary: str
    target_business_types: list[str]            # Arabic + English phrasings, e.g. "kids clothing store" and its Arabic form
    include_keywords: list[str]; exclude_keywords: list[str]
    google_place_types: list[str] = []          # e.g. ["clothing_store", "baby_store"]
    regions: list[RegionTarget]
    business_size: Literal["micro", "small", "medium", "large", "any"] = "any"
    must_have: list[str]; nice_to_have: list[str]; disqualifiers: list[str]
    value_proposition: str; pain_points: list[str]; outreach_angle: str
    language: str = "ar-EG"

class GeneratedQuery(BaseModel): query: str; region: RegionTarget; rationale: str
class QueryPlan(BaseModel): queries: list[GeneratedQuery]          # 5–15 queries

class LeadScore(BaseModel):
    lead_ref: str                    # the lead id as a string
    score: int                       # 0..10
    fit: Literal["fit", "partial", "not_fit"]
    reasons: list[str]               # 1–4 short reasons
    disqualify_reason: str | None = None
class LeadScoreBatch(BaseModel): scores: list[LeadScore]

class PersonalizedOpening(BaseModel):
    template_params: list[str]       # exactly param_count items; no newlines/tabs; ≤ 60 chars each
    preview_text: str                # rendered message for the approval UI
    rationale: str

class ReplyClassification(BaseModel):
    intent: ReplyIntent; confidence: float; summary: str
    requested_discount_percent: int | None = None
    asks_for_human: bool = False; language: str = "ar-EG"
```

## 9. Services shared across tasks (signatures fixed; owner implements)

```python
# app/services/messaging.py  (P3-2)
async def create_outbound(session, *, tenant_id, lead_id, purpose: OutreachPurpose, kind: MessageKind,
                          body: str, template_name: str | None = None, template_params: list[str] | None = None,
                          author: MessageAuthor = MessageAuthor.AGENT, needs_approval: bool,
                          agent_run_id: UUID | None = None) -> Message
    # status = pending_approval if needs_approval else queued (and enqueues job_send_message).
    # Refuses (status=blocked) if the lead is opted_out.
async def approve_message(session, *, tenant_id, message_id, user_id, edited_params: list[str] | None = None,
                          edited_body: str | None = None) -> Message
async def reject_message(session, *, tenant_id, message_id, user_id) -> Message
async def send_message(message_id: UUID) -> None
    # job body: checks opt-out, the 24h window for free text, demo redirect, then calls the adapter and updates the status.
def resolve_demo_target(settings, lead_id) -> str | None   # whitelisted phone (writes demo_routes)

# app/services/autonomy.py  (P3-3)
def needs_approval(settings: BusinessSettings, purpose: OutreachPurpose) -> bool
    # approve_all → True for all; approve_first_touch → True only for FIRST_TOUCH; autopilot → False

# app/services/notifications.py  (P3-4 minimal, P4-2 full)
async def notify_owner(session, *, tenant_id, kind: str, title: str, body: str, lead_id: UUID | None = None) -> None

# app/services/knowledge.py  (P1-1)
async def get_knowledge_text(session, tenant_id, max_chars: int = 120_000) -> str   # concatenated ready files
async def search_knowledge(session, tenant_id, query: str, k: int = 5) -> list[str] # keyword/paragraph search

# app/services/icp_service.py  (P1-3)
async def get_active_icp(session, tenant_id) -> IcpVersion | None

# app/services/insights.py  (stub in P2-3 returns []; real in P4-4)
async def get_active_insights(session, tenant_id) -> list[str]
```

## 10. Jobs (`app/workers/jobs/*.py`; names fixed)

| Job | Args | Owner | Chains to |
|---|---|---|---|
| `job_build_icp` | tenant_id, run_id=None | P1-3 | — |
| `job_run_sourcing` | tenant_id, max_results, run_id=None | P2-2 (orchestration), P2-1 (query+search) | `job_score_leads` |
| `job_score_leads` | tenant_id, run_id | P2-3 | `job_enrich_leads` |
| `job_enrich_leads` | tenant_id, lead_ids | P3-1 | — |
| `job_outreach_tick` | (cron every 5 min, all tenants) | P3-3 | `job_send_message` |
| `job_send_message` | message_id | P3-2 | — |
| `job_handle_inbound` | message_id | P3-4 (stub by P3-2) | — |
| `job_daily_cycle` | (cron 09:00 Africa/Cairo) | P2-2 | `job_run_sourcing` per enabled tenant |
| `job_feedback` | tenant_id | P4-4 | — |

Enqueue helper: `app/workers/queue.py: async def enqueue(job_name: str, **kwargs) -> str`.

## 11. API routes (all under `/api/v1`)

| Method & path | Purpose | Owner |
|---|---|---|
| POST `/auth/register` {email, password, full_name, company_name} | create tenant + owner + default settings | P0-4 |
| POST `/auth/login`, POST `/auth/logout`, GET `/auth/me` | | P0-4 |
| GET/PUT `/settings` ; GET `/settings/geo` (governorates + cities constant) | business settings | P1-2 |
| POST `/knowledge` (multipart), GET `/knowledge`, DELETE `/knowledge/{id}` | files | P1-1 |
| POST `/icp/generate` → {run_id} ; GET `/icp/active` ; GET `/icp/versions` ; PUT `/icp/active` {company_profile, icp, notes} → new version source=user | | P1-3 (API), P1-4 (UI) |
| POST `/runs/sourcing` {max_results?} → {run_id} | "Run agent now" | P2-2 |
| GET `/runs?kind=&page=` ; GET `/runs/{id}` (with steps) | Agent Activity | P0-3 (API), P2-4 (UI) |
| GET `/leads?status=&min_score=&q=&governorate=&sourcing_run_id=&sort=&page=` ; GET `/leads/stats` (counts per status) ; GET `/leads/{id}` (contacts, messages, history, notes, outcome) | | P2-4 list + stats, P4-1 detail |
| PATCH `/leads/{id}` {status?, agent_paused?} ; POST `/leads/{id}/notes` ; POST `/leads/{id}/outcome` {outcome, value_egp?, reason?} ; POST `/leads/{id}/contacts` {type, value} | CRM actions | P4-1 |
| POST `/leads/{id}/messages` {body} | manual WhatsApp text inside the 24h window | P4-1 |
| GET `/leads/export.xlsx` | Excel export | P4-1 |
| GET `/outreach/queue` ; POST `/outreach/messages/{id}/approve` {params?, body?} ; POST `/outreach/messages/{id}/reject` ; POST `/outreach/approve-bulk` {ids} | approvals | P3-3 |
| GET `/channels` ; PUT `/channels/whatsapp` {phone_number_id, waba_id, access_token} ; POST `/channels/whatsapp/test` {to} ; POST `/channels/whatsapp/templates/sync` | | P3-2 |
| GET/POST `/webhooks/whatsapp` | Meta webhook (verify + events) | P3-2 |
| POST `/channels/telegram/link` → {deep_link} ; POST `/webhooks/telegram` | | P4-2 |
| GET `/notifications` ; POST `/notifications/{id}/read` ; POST `/notifications/read-all` | | P4-2 |
| GET `/dashboard` | home summary | P4-2 |
| GET `/reports/summary?from=&to=` ; `/reports/funnel` ; `/reports/segments?by=governorate\|category\|score_band` ; `/reports/costs` ; `/reports/timeseries?metric=` | | P4-3 |
| GET `/insights` ; POST `/insights/run` ; POST `/insights/{id}/deactivate` | feedback loop | P4-4 |

## 12. Demo routing (P3-2)
When `settings.demo_mode` is true, `send_message` sends to `resolve_demo_target(...)` instead of the lead's number:
- It picks the whitelisted phone that has been unused for longest (or the one already routed to this lead), upserts `demo_routes(test_phone → lead_id)`, and stores it in `messages.redirected_to`.
- An inbound message from a whitelisted phone is attributed to `demo_routes[test_phone].lead_id`.
- If the whitelist is empty, sending is blocked (`status=blocked`, error `demo_whitelist_empty`).

## 13. Environment variables (`.env.example`)
```
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/app
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=change-me
ENCRYPTION_KEY=                      # Fernet key: python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
PUBLIC_BASE_URL=https://<your-tunnel>.trycloudflare.com
USE_MOCK_ADAPTERS=true
USE_MOCK_LLM=true
ANTHROPIC_API_KEY=
MODEL_SMART=claude-opus-5-5
MODEL_FAST=claude-haiku-5-5
GOOGLE_PLACES_API_KEY=
WHATSAPP_APP_SECRET=                 # Meta app secret (webhook signature)
WHATSAPP_VERIFY_TOKEN=               # any random string, same as in the Meta dashboard
WHATSAPP_GRAPH_VERSION=              # check Meta docs for the current version, e.g. v2x.0
TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=
UPLOAD_DIR=./data/uploads
```
