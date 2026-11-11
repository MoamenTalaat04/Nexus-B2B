# Architecture

## 1. From the reference architecture to ours

The reference "B2B Growth Engine" glues together a dozen SaaS tools and needs a technical operator. We keep the same **layers** but ship them as one product, with every external system behind an adapter interface.

| Layer | Reference stack | Our implementation | Replaceable via |
|---|---|---|---|
| 00 Intent signals | Bombora, RB2B/Warmly | Not in MVP (future: our own website pixel) | — |
| 01 Data ingestion | Apollo, Apify | `SearchSource` → Google Places API (New); `Enricher` → our website crawler | `adapters/search`, `adapters/enrichment` |
| 02 AI core ("brain") | Claude | Our orchestrator: arq jobs + state machine + LLM nodes | `adapters/llm` via `agents/llm.py` |
| State / data backbone | Supabase | Our PostgreSQL schema | — |
| Analytics | Metabase | Reports module in the app | — |
| 03 Activation | Smartlead, HeyReach, WATI/360Dialog | `ChannelAdapter` → WhatsApp Cloud API (email later) | `adapters/channels` |
| 04 CRM | HubSpot | Built-in CRM (table, kanban, lead detail, actions) | — |
| Feedback loop | HubSpot → Supabase → Claude | Outcomes → learned insights → scoring prompt | — |

## 2. Why a workflow agent and not one autonomous agent (ADR-001)

**Decision:** the agent is a **deterministic workflow** (jobs + a lead state machine). The LLM is called only at decision points: building the ICP, generating queries, scoring, personalizing, classifying replies, and conversing.

**Why:**
- **Reliability:** each lead is always in a known state, and a crash resumes from that state.
- **Cost:** most steps are plain code. The LLM runs only where judgment is needed, and bulk steps use the cheap model.
- **Testability:** each LLM node has a typed input/output (structured outputs), so it can be unit-tested with mocks and **evaluated** with datasets.
- **Safety:** humans can gate the steps that matter (sending) without stopping the rest.

**Where we do use a true agent loop:** the **Reply Agent** (P3-4). Conversations are open-ended, so the model gets a small set of scoped tools and decides what to do, inside guardrails.

## 3. The daily cycle

```
           ┌──────────── owner input ────────────┐
           │ files (PDF/MD/TXT/DOCX) + onboarding │
           └───────────────────┬──────────────────┘
                               ▼
                   [ICP Builder agent]  → icp_versions (company_profile + icp)
                               │
        cron 09:00 Cairo / "Run agent now"
                               ▼
  [Query Generator] → [Google Places] → [normalize + dedupe] → leads(status=new)
                               ▼
                    [Lead Scorer (FAST model)] → qualified | disqualified (+reasons)
                               ▼
                [Enrichment: Places phone + website crawler] → contacts → enriched | no_contact
                               ▼
         cron every 5 min: [Outreach tick]
           picks due leads → [Message personalizer]
           ├─ first_touch_mode = assisted (default): free-text message → awaiting_manual_send
           │     → owner taps "Open in WhatsApp" on their phone, sends, taps "I sent it"
           │     (message includes a link to our AI assistant number + the lead's #ref code)
           └─ first_touch_mode = api_template (demo / opted-in leads): template message
                 → needs_approval? → pending_approval → (human approves) → queued → send
                               ▼
                 WhatsApp Cloud API ──► lead's phone (DEMO_MODE → team phone)
                               │
              webhook ◄────────┘ inbound reply / delivery statuses
                               ▼
     [Reply classifier (FAST)] → status (interested / wants_offer / …)
                               ▼
     [Reply Agent (SMART, tools)] → answer / escalate / schedule follow-up / stop
                               ▼
               CRM + notifications (in-app + Telegram) + reports
                               ▼
        owner marks won/lost → [Feedback job] → learned insights → scorer
```

## 4. Lead lifecycle (state machine)

```
new ──► qualified ──► enriched ──► queued ──► contacted ──► replied ──► {interested, not_interested,
 │          │             │                       │                     wants_offer, wants_management,
 ▼          ▼             ▼                       │                     later, wrong_contact}
disqualified  no_contact  (no mobile)             │                              │
                                                  └── (sequence ends, no reply) stays contacted
any non-terminal ──► opted_out (terminal, never message again)
interested / wants_* / later / contacted / replied ──► won | lost (set by the owner)
later ──► contacted (when the follow-up is due)
```
The full allowed-transition table is in CONTRACTS.md §4.

`agent_paused = true` on a lead means a human has taken over: the agent stops sending messages to that lead. It is set automatically on escalation (`interested`, `wants_management`, an offer above the allowed discount).

## 5. Runtime components

| Process | What it runs |
|---|---|
| `api` (FastAPI) | REST API, auth, webhooks (WhatsApp, Telegram) |
| `worker` (arq) | All agent jobs + cron (`daily_cycle`, `outreach_tick`) |
| `web` (Next.js) | Owner UI |
| `db` (Postgres), `redis` | State and job queue |

## 6. Observability

Every job opens an `agent_run` and writes `agent_steps` (LLM call, tool call, external API call, decision, error) with tokens, cost (USD), latency, and the related lead. The **Agent Activity** page renders this. **Reports** aggregate it into cost per qualified lead.

## 7. Safety & guardrails summary

| Risk | Guardrail |
|---|---|
| Messaging real businesses during development | `demo_mode` (default on) redirects every outbound message to whitelisted phones |
| WhatsApp number bans | Official Cloud API only, approved templates for the first touch, `daily_send_cap`, quiet hours |
| Prompt injection from lead messages / web pages | XML-wrapped untrusted content, tools bound to one lead server-side, no tool can change settings, safety eval suite |
| Agent inventing prices or discounts | Reply agent answers only from the company profile + knowledge; discount above `max_discount_percent` → escalate |
| Spamming people who said stop | `opted_out` is terminal and checked at send time |
| Runaway cost | Model routing (smart vs fast tier), free tier in development, stable prompt prefixes for provider caching, effort settings, per-run cost tracking |
| WhatsApp bans / cold-messaging rules | Default first-touch mode is **assisted**: the owner sends the first message personally, at low volume, and invites the lead to message our assistant number. The API sends templates only in demo mode or to opted-in leads. Lead-initiated chats are attributed by `#ref_code`. |
| Provider lock-in | Every LLM call goes through `app/adapters/llm/`; switching provider is a config change |
| Legal (Egypt PDPL 151/2020) | Record source of every contact, honor opt-out, store only business contact data |

## 8. Future (not in this month)
Email and Telegram outreach channels, Meta Embedded Signup, Facebook/Instagram page discovery, intent pixel, voice agent, billing/plans, Arabic UI.
