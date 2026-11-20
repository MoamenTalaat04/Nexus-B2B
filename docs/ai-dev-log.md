# AI Development Log

We build this project with coding agents (Claude Code + Claude Opus 5.5). After **every task**, the owner appends one entry. This log becomes the "how we used agentic engineering" part of the final presentation, so be honest. The mistakes are the most valuable part.

## Running totals (update at the end of each pipeline)

| Pipeline | Tasks | Agent sessions | Est. hours saved | Bugs caught by AI review | Bugs caught at slice demo | Contract changes |
|---|---|---|---|---|---|---|
| P0 | | | | | | |
| P1 | | | | | | |
| P2 | | | | | | |
| P3 | | | | | | |
| P4 | | | | | | |

## Entry template

```
### <task id> — <title> — <owner> — <date>
- Sessions / approx. time: 
- Plan-mode corrections I made (where the agent misread the task/contract):
- What the agent did well:
- What it got wrong and how I caught it (tests? review? running it?):
- Prompt tweaks that helped (copy the exact sentence):
- Eval result (if any): suite, score before → after
- Would I do it differently next time?
```

## Entries

### P0-0 — Repo scaffold, tooling, CI — Claude (Claude Code, Opus 5.5) — 2026-11-11
- Sessions / approx. time: 1 session, about 1 hour including toolchain setup on a fresh Windows machine.
- Plan-mode corrections: the repo's first README proposed a different stack (NestJS, Prisma, BullMQ, Vite). The human chose to keep the planned stack (FastAPI, Next.js, WhatsApp first), and the README was rewritten to match.
- What the agent did well: router and job auto-discovery, so later tasks never edit `main.py` or the worker settings; tests run on a separate `app_test` database with per-test rollback; it verified the worker end to end by enqueueing `job_ping`.
- What it got wrong and how it was caught: (1) `import app.api` clashed with the `app = FastAPI()` variable (caught by mypy); (2) `uvicorn --reload` watched `.venv` and kept reloading (caught by running the server; fixed with `--reload-dir app`); (3) arq logs were printed twice (caught by reading the worker output); (4) `@vitejs/plugin-react` had a peer-dependency conflict with the current Babel, so Vitest uses its built-in JSX transform instead.
- Notes for teammates: on Windows PowerShell, `npm` may be blocked by the execution policy. Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once or use `npm.cmd`. The scaffold uses Next.js 16, whose APIs differ from older versions; read `frontend/AGENTS.md`.
- Would I do it differently next time? Pin the frontend tool versions in the task prompt to avoid peer-dependency surprises.

### P0-3 — LLM wrapper, provider adapter, pricing, tracing & runs API — Member C (Claude Code, Opus 5.5) — 2026-11-18
- Sessions / approx. time: 1 session, about 2 hours. Mock mode only: no free LLM key in `.env` yet, so the real-call self-check is still open.
- Plan-mode corrections: P0-2 (tables) and P0-4 (auth) were not on `main` yet, so P0-3 adds minimal stand-ins that follow their specs: `models/enums.py` (every enum from the contract), `models/tenants.py` (`tenants` only), `models/runs.py`, migration `0002`, and a read-only `core/security.get_current_user`. B and D own those files and extend them.
- What the agent did well: traces commit in their own transaction (tested against a real rollback); the test `session` fixture points trace writes at the same connection, so job tests see their own data and roll back cleanly.
- What it got wrong and how it was caught: (1) the installed openai SDK sends requests through `httpx2`, which respx does not patch; caught by the adapter tests failing with real DNS lookups. The tests now inject an `httpx2.MockTransport`. (2) `now()` is the same for every row in one transaction, so "newest first" was random in tests; trace rows now get `created_at` from Python. (3) nested Pydantic models in step payloads were stored as strings; caught by a test, fixed with `pydantic_core.to_jsonable_python`.
- Prompt tweaks that helped: none yet (no prompts in this task).
- Eval result: n/a.
- Open items: run the self-check with the real key (one call per tier, a tool call, 10 calls at once). Update: the suggested Gemini models' paid prices were added to `pricing.py` on 2026-11-18 (source: Google's pricing page).

### P1-3 — Company Profile & ICP builder agent — Member C (Claude Code, Opus 5.5) — 2026-11-18
- Sessions / approx. time: same session as P0-3, about 1.5 hours. Mock LLM only (no key yet), so the real-ICP review the task asks for is still open.
- Plan-mode corrections: `business_settings` (P0-2), `app/core/tenancy.py` (P0-2) and `services/knowledge.py` (P1-1) were not on `main`. Added contract-exact stand-ins for the first two (migration `0003` also creates `icp_versions`), and the job loads A's knowledge service only if it exists (TODO marked).
- What the agent did well: both LLM calls share one identical stable prefix (system prompt + settings YAML + `<company_files>`), proven by a spy test; code guardrails make the owner's settings win (regions, discount, offers, tone), and each change is traced as a DECISION step; a partial unique index guarantees exactly one active ICP per tenant.
- What it got wrong and how it was caught: (1) a first draft of `business_settings` tried to override the mixin's `tenant_id` in a convoluted way; caught on re-read before running, and replaced with an explicit unique column. (2) Arabic output crashed `print` in the Windows console during the manual check (cp1252); fixed with `PYTHONIOENCODING=utf-8` (not an app bug).
- Manual check: POST /icp/generate → real Redis queue → `arq --burst` worker → v1 saved in 0.14 s (mock LLM) → owner edit via PUT → v2 active, v1 inactive.
- Eval result: none yet (D owns the icp eval suite in P1-4).
- Open items: generate an ICP with the real model from the demo business files and share the JSON with the team; run the self-check on two very different businesses (look for invented facts).

### P2-1 — Query generator + Google Places adapter — Member C (Claude Code, Opus 5.5) — 2026-11-18
- Sessions / approx. time: same session, about 1 hour. Mock LLM and mocked HTTP only: there is no Google Places key yet, so `try_places.py` has not been run against Google.
- Plan-mode corrections: A's `adapters/base.py` + `registry.py` (P0-1) and B's `search_queries` table (P0-2) were not on `main`. Added stand-ins: base.py with every model/Protocol from CONTRACTS §7, a registry with only `get_search_source` (mock mode names P0-1 until A's mock lands), `models/leads.py` with only `SearchQuery`, migration `0004`.
- Facts checked before coding (Google's Text Search docs, 2026-11-18): field mask header format, pageSize ≤ 20, ≤ 60 results per query, locationBias radius ≤ 50 km, and that every parameter except the page token must stay the same between pages (a test asserts this).
- What the agent did well: post-processing in code (ICP regions, Arabic-normalized dedupe, already-used, cap 15) with a DECISION step listing what was dropped; Arabic `addressComponents` mapped back to the English governorate names the app uses; `last_request_count` counts only successful (billable) requests.
- What it got wrong and how it was caught: (1) a first version let a query with no city escape to the whole governorate when the ICP limits cities; caught on re-read, now it stays inside the ICP's cities (tested). (2) the name-lookup helper first came out convoluted (two normalizers); simplified and the Arabic normalizer is now shared by the geo lookup and the query dedupe. (3) ruff's "ambiguous character" rules flag every Arabic letter; now ignored project-wide since Arabic is normal here.
- Unverified: the governorate/city center coordinates are approximate (used only as a soft location bias), and which `addressComponents` types Google returns for Egyptian addresses (code falls back to the RegionFilter).
- Open items: run `uv run python -m scripts.try_places "kids clothing shop" --governorate Cairo` (and the Arabic phrasing) with the real key and paste the names into the summary; B's sourcing job (P2-2) calls `generate_queries` + `get_search_source().search`.

### P3-3 — Outreach engine, personalization, autonomy & approval queue (backend) — Member C (Claude Code, Opus 5.5) — 2026-11-19
- Sessions / approx. time: same session, about 2 hours. Backend only; the /outreach frontend waits for D's app shell (P0-4). Mock LLM only; nothing is sent (B's messaging is a stand-in).
- Plan-mode decision (with the human): build the backend now with thin stand-ins instead of everything (the frontend shell is too opinionated to stand in for without big merge conflicts) or waiting a week.
- Stand-ins written to the contract for B/D: leads, contacts, lead_status_history (models/leads.py), channel_connections, message_templates, conversations, messages (models/messaging.py), notifications, core/lead_state.py (the §4 table verbatim), core/refcodes.py, migration 0005; services/messaging.py with every §9 signature but it NEVER sends (no enqueue, send_message is a no-op); services/notifications.notify_owner (row only).
- What the agent did well: the tick is fully deterministic code (window, cap, due selection with SKIP LOCKED, open-message guard, sequence steps) and the LLM only fills params/text; every model answer is checked in code (param count, ≤ 60 chars, one line, no prices/links) with one retry and a safe generic fallback; the assistant link line is added by code; a real two-connection test proves two concurrent ticks never double-message.
- What it got wrong and how it was caught: (1) a first draft called rollback() inside the tick when there was no work, which would have discarded the caller's data in tests; caught on re-read. (2) the daily-cap test failed because messages take created_at from the database clock while the test simulates a future Monday; the code was right, the test now moves created_at to the simulated day. (3) a test asserted 08:30 UTC is outside 10:00–20:00 Cairo; it is 10:30 in Cairo (UTC+2); fixed. (4) `Result.tuples()` is deprecated in SQLAlchemy 2.1; replaced.
- Design notes for the team: the personalizer rationale has no column in `messages`, so it is stored on the run's DECISION step "outreach.message" and joined by message_id (no contract change); `POST /outreach/messages/{id}/mark-sent` accepts an optional {body} with the owner's final text (additive).
- Open items: the /outreach frontend (approval cards, "To send" mobile tab, usePendingApprovals + sidebar badge with D); B's real messaging must call `outreach.on_message_sent(session, message)` after a successful send; personalizer eval with the real model.

### Real-model checks (P0-3 self-check + P1-3 real ICP) — Member C — 2026-11-19
- Gemini free tier via the OpenAI-compatible endpoint (gemini-4-hydrogen SMART, gemini-3.5-flash-lite FAST), fictional data only.
- `scripts/llm_smoke.py` passed: FAST + SMART structured output, a tool call, 10 concurrent calls (Google returned some 503s; the wrapper's retries absorbed them). Run cost ≈ $0.003 at paid prices.
- Bug found by the real run: Gemini 3+ needs the tool call's thought signature sent back on the next turn (HTTP 400 otherwise); fixed in the adapter (`provider_extra`), with a test.
- `scripts/try_icp.py` generated a real ICP from the fictional kids-clothing business: facts only (unknown price left null), Arabic + English Maps phrasings, competitors as disqualifiers, regions inside the owner's choice (guardrails changed nothing). 2 calls, ~20 s, ≈ $0.017 at paid prices. Result for team review: `docs/examples/icp-demo-gemini.json`.
- Observation: cached input tokens were 0 on the second call even with an identical prefix; the provider may need a longer prefix before it caches (unverified; check Gemini's implicit-caching docs before relying on it in the cost story).

### P1-3 self-check: second, very different business — Member C — 2026-11-19
- `scripts/try_icp.py --business medical`: a fictional medical-supplies *distributor* in Alexandria selling to clinics, English + Arabic notes, tone "formal", and deliberately no prices or minimum orders.
- Result (`docs/examples/icp-demo-gemini-medical.json`): no invented facts — every price/min order stayed null and the automatic "numbers not in the inputs" check found none; FAQs only from stated facts; competitors (other distributors) and equipment companies excluded per the owner's "consumables only"; regions kept to Smouha/Mansheya; Maps phrasings in Arabic + English, place types dentist/doctor. 2 calls, ≈ $0.015 at paid prices.
- Watch item: with tone "formal" the model wrote Modern Standard Arabic, not Egyptian Arabic. Fine inside the ICP, but outreach and replies must stay Egyptian Arabic (CLAUDE.md) — keep that explicit in the personalizer and reply-agent prompts and in D's reply eval.

### P2-1 self-check: real Google Places results (free Maps Demo Key) — Member C — 2026-11-19
- Key: Google Maps Platform **Maps Demo Key** (free, no billing; supports Places API (New); daily limits only pause usage, never charge; meant for testing/prototyping, which fits the demo). It returns the Enterprise fields we need (phones, website, rating).
- `try_places.py "محل ملابس اطفال" --governorate Cairo --city "Nasr City"`: 20 shops, 19 with a phone, 1 request. Names: روز كيدز - عباس العقاد (Rose Kids), Ninos Kids — Abbas El-Akkad, Pinky Lollypop, جونيور, Child Mall, Aya kids, لفلي, تو إس لملابس البيت, بيبى لاند, ضجة, Kidzvilla, Kids Park store, Junior, Our Kids, كلارك كيدز, صن بيبي, Alsayad Kids, Pinky, Our Kids (Dokki), ريم ورحاب لتجهيزات البيبي.
- `try_places.py "kids clothing shop" --governorate Cairo`: 20 shops, 18 with a phone, 1 request (Our Kids, Ninos Kids branches, junior, Child Mall, Lovely Stores, pink and blue, Cotton House, Bambi Kids Wear, Rashdan, Karas Kids, …).
- Overall 37/40 (93%) have a phone number — versus 1/21 on OpenStreetMap around Nasr City.
- For the next steps: location bias is not a filter (a Cairo search returns some Giza shops, correctly labelled Giza); wholesalers appear (e.g. «مكتب المالكى للملابس جمله وقطاعى») — A's scoring should disqualify them per the ICP; chains appear as several branches — B's dedupe; phones come in local format (010…) — B normalizes to E.164; cities come in Arabic.

### P0-2 · P1-2 · P2-2 · P3-2 · P4-4 — Member B backend (one session, branch `Task-B`) — Member B (Claude, Opus 5.5) — 2026-11-20
- Sessions / approx. time: one long session for all five backend tasks, on branch `Task-B` off `main` (e50acac).
  The session's sandbox had **no network for package installs**, so FastAPI/SQLAlchemy/pytest were not
  available: code was checked with `ruff check` + `ruff format --check` and `py_compile` only. **`uv run poe check`
  (mypy + pytest) has not run yet — run it before merging.**
- P0-2: kept C's stand-ins (they match §3) and added `users`, `lead_notes`, `lead_outcomes`, `demo_routes`,
  `learned_insights` in migration `0006` (revises `0005`, hand-written in the autogenerate style); `core/crypto.py`
  (Fernet, clear errors for a missing/invalid key), `tenancy.scoped()`, `scripts/export_enums.py` (deterministic,
  `--out` / `--check`; D commits `frontend/src/lib/types.ts`), `models/README.md` with the ER diagram; tests for
  every transition pair, crypto, constraints and an upgrade → downgrade → upgrade migration run.
- P1-2: `GET/PUT /settings` (partial update; only an owner can write), `GET /settings/geo` (27 governorates, cities
  for the 7 main ones, names aligned with C's `geo_eg_coords.py`). Cross-field checks after merging with the
  stored row (quiet hours, onboarding completeness). Handoff for D: `docs/api/member-B-endpoints.md`.
- P2-2: `core/phones.py`; `services/leads_ingest.py` (priority dedupe key + "same mobile on another lead"
  check; one preload + one bulk `INSERT … ON CONFLICT DO NOTHING`, query count asserted ≤ 4); `job_run_sourcing`
  (one failing search = an ERROR step, not a failed run), `job_daily_cycle` (09:00 Cairo, working days only,
  arq `_job_id` per tenant/day), `POST /runs/sourcing` (409/400/503). `leads.raw` stores the whole PlaceResult plus
  `phone_e164`, so enrichment can create the contact without calling Google again.
- P3-2: `adapters/channels/whatsapp_cloud.py` (Graph API send/check/templates, Meta error codes → short codes,
  retries only on 429/5xx, param sanitising, webhook signature + parser), `adapters/channels/mock.py`,
  `registry.get_channel/build_channel/ChannelNotConnected`, the real `services/messaging.py` (guardrails at send
  time, LRU demo routing that writes `demo_routes`, `#REFCODE` lead-initiated chats, STOP words → OPTED_OUT
  first, status ordering), `job_send_message` + stub `job_handle_inbound` + a sweeper cron, the channels API and the
  webhook, `docs/setup-whatsapp.md` (written new; there was no first version on main).
- P4-4: `services/insights.py` (stats per segment in code), `agents/feedback.py` + `prompts/feedback.md`
  (`feedback@1`, SMART/medium, untrusted `<examples>` without phones), `job_feedback`, `/insights` API,
  `scripts/seed_demo.py` (idempotent, `--reset`), `tests/e2e/test_full_cycle.py`, `docs/DEMO-SCRIPT.md`.
- Decisions to review with the team (no contract file was edited):
  1. Unknown-sender notifications use kind `channel_error` (the §3 CHECK has no better kind).
  2. Quiet hours at send time keep the message queued and re-enqueue it for the next window, but do **not** touch
     `lead.next_action_at` (the prompt asked for it) — C's outreach engine uses that column for the sequence, and
     overwriting it would move the follow-up.
  3. Additive route `PUT /channels/whatsapp/templates/{id}` so the owner can tag a template intro/followup.
  4. `resolve_demo_target(settings, lead_id, routes=None)`: C's assisted wa.me code calls it synchronously, so
     without routes it stays the stable per-lead pick; `route_demo()` is the async LRU version that writes
     `demo_routes` (used by `send_message` and `mark_sent_manually`).
  5. `registry.py` belongs to P0-1, but P3-2 needed `get_channel`; only that part was added.
- What is still missing / depends on others: the mock search source (`adapters/search/mock.py`, P0-1) — until it
  lands, `USE_MOCK_ADAPTERS=true` sourcing raises NotImplementedError (tests use a fake source); A must call
  `insights.on_outcome_recorded(session, tenant_id)` after committing an outcome in `POST /leads/{id}/outcome`
  (P4-1) and read `get_active_insights` in the scorer (P2-3); the e2e test uses marked stand-ins for P0-4, P1-1,
  P2-3, P3-1, P3-4 and P4-1; `knowledge_files` is P1-1's table, so the seed writes the profile file to
  `UPLOAD_DIR` and inserts the row only when that model exists.
- Would I do it differently next time? Get a working `uv sync` first: five tasks of code without one pytest run is
  the biggest risk in this branch.

## P3-3 · real WhatsApp send self-check (Nov 20, Moamen Talaat / C)
- After merging Task-B (B's real messaging, P3-2), ran `scripts/try_outreach_send.py` against the real Cloud API:
  demo tenant, ICP from `docs/examples/icp-demo-gemini.json`, templates synced from Meta (`intro` / `followup`
  approved, purposes tagged automatically), 3 fictional enriched leads, outreach tick with real Gemini personalization
  (`approve_first_touch` → 3 pending), approve, send.
- Result: 3/3 `sent`, all redirected to the team test phone (demo mode), leads ENRICHED → QUEUED → CONTACTED through
  `outreach.on_message_sent`. Gemini returned three 503s on the first call; the wrapper retried them.
- The model dropped the "(تجريبي)" suffix from shop names and named each area in Arabic, within the param rules.
- Not done yet: replies (needs the webhook tunnel), then "stop" → opted_out.
