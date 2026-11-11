# Member B — Task Prompts

**Your tasks:** P0-2 Data model & state machine · P1-2 Onboarding & settings · P2-2 Normalize, dedupe, sourcing job · P3-2 WhatsApp channel · P4-4 Feedback loop & demo seed ⭐
**Before every task:** read `00-START-HERE.md` §4. Paste only the part between the `~~~text` fences into Claude Code, **in plan mode**, from the repo root.

---

## P0-2 · Data model, migrations, state machine, tenancy — Wed Nov 11 → Fri Nov 13
**Start:** right away; the repo scaffold (P0-0) is already on `main`.
**Files you own:** `backend/app/models/*` (except base.py, which already has `Base` and the mixins), `backend/app/models/enums.py`, `backend/alembic/versions/*` (first migration), `backend/app/core/lead_state.py`, `backend/app/core/tenancy.py`, `backend/app/core/crypto.py`, `backend/app/core/refcodes.py`, `frontend/src/lib/types.ts` (enums mirror only), tests.

~~~text
Read CLAUDE.md and docs/CONTRACTS.md completely first. CONTRACTS.md §2, §3, §4 and §5 define exactly what you build —
use the exact table names, column names and enum values. If you believe something in the contract is wrong or
missing, stop and tell me instead of changing it.

1. app/models/enums.py: every StrEnum from CONTRACTS §2, plus the INTENT_TO_STATUS mapping dict.
2. SQLAlchemy 2.0 typed models (Mapped[...]) for every table in §3, grouped in files: tenants.py (tenants, users,
   business_settings), knowledge.py, icp.py, runs.py (agent_runs, agent_steps), leads.py (search_queries, leads,
   contacts, lead_status_history, lead_notes, lead_outcomes), messaging.py (channel_connections, message_templates,
   conversations, messages, demo_routes), notifications.py (notifications, learned_insights).
   Enums are stored as text with CHECK constraints generated from the StrEnum values. All the FKs, unique
   constraints and indexes from the contract; also add indexes on leads(tenant_id, status),
   leads(tenant_id, next_action_at), messages(tenant_id, lead_id, created_at), agent_steps(run_id, seq).
   JSONB defaults exactly as specified (e.g. sequence_steps, demo_whitelist). Use server defaults where possible.
3. The first Alembic migration (autogenerate, then review by hand: CHECK constraints, gen_random_uuid(), the int[]
   default for working_days, an updated_at trigger or ORM onupdate — pick one and be consistent).
4. app/core/lead_state.py: the ALLOWED table and transition(...) exactly as in §4, including "any non-terminal →
   OPTED_OUT", "classified statuses → REPLIED on a new inbound", force only for actor="user", and an
   InvalidTransition exception. Writes lead_status_history in the same session (no commit inside — the caller commits).
5. app/core/tenancy.py: get_settings_for(session, tenant_id) (creates a default business_settings row if missing)
   and a small helper `scoped(select_stmt, model, tenant_id)` that adds the tenant filter.
6. app/core/crypto.py: encrypt_json / decrypt_json with Fernet from settings.ENCRYPTION_KEY (a clear error if the
   key is missing).
7. frontend/src/lib/types.ts: TypeScript string-union mirrors of every enum (generate them with a small script
   backend/scripts/export_enums.py so they never drift; document how to rerun it).
8. Tests: migration upgrade/downgrade on an empty DB; transition() allowed and forbidden cases (table-driven,
   covering every status), the opted_out terminal rule, history row creation; crypto round-trip; the unique
   constraint on (tenant_id, dedupe_key).

Also add backend/app/models/README.md with an ER summary (a mermaid erDiagram of the main tables). Run poe check.
~~~
**Definition of done:** `uv run poe migrate` creates every table; transition tests cover the whole table; the enums are mirrored in TS.
**Self-check before you push:** compare each table with CONTRACTS §3 column by column (yes, all of them; this prevents a month of bugs).

---

## P1-2 · Onboarding wizard & business settings — Sat Nov 14 → Wed Nov 18
**Files you own:** `backend/app/api/settings.py`, `backend/app/schemas/settings.py`, `frontend/src/app/(app)/onboarding/*`, `frontend/src/app/(app)/settings/page.tsx` + `settings/business/*` + `settings/agent/*`, `frontend/src/hooks/useSettings.ts`, tests.

~~~text
Read CLAUDE.md and docs/CONTRACTS.md (§3 business_settings, §11 /settings) first.

Our users are non-technical business owners (e.g. a kids-clothing factory owner). Onboarding must feel like
talking to a new sales employee: "tell me about your business, your products, and who you sell to".

Backend:
1. GET /api/v1/settings and PUT /api/v1/settings (partial update) with Pydantic validation:
   products 1–30 items; target_regions use a fixed list of the 27 Egyptian governorates (English names, with Arabic
   labels in a constant in app/core/geo_eg.py, plus the main cities/districts for Cairo, Giza, Alexandria,
   Qalyubia, Sharqia, Dakahlia, Gharbia); max_discount_percent 0–50; daily_send_cap 1–200 (warn above 50 in the
   UI); quiet hours start < end; demo_whitelist entries normalised to E.164 (+20…) and at most 5 (the WhatsApp test
   number limit); score_threshold 1–10; sequence_steps validated (1–4 steps, increasing day_offset, first purpose
   first_touch). Tenant from the auth user only. Tenant-isolation test.
2. Expose GET /api/v1/settings/geo returning the governorates/cities constant for the UI.

Frontend:
3. /onboarding — a 5-step wizard with a progress bar, Back/Next, and autosave on each step:
   (1) Company: name, website, short description, language (Egyptian Arabic / English), tone.
   (2) Products: repeatable rows (name, description, price range, minimum order).
   (3) Knowledge: embed A's <KnowledgeUploader/> (import from components/knowledge; if A has not merged yet, show a
       placeholder card and leave a TODO with the import path).
   (4) Targets: governorates + cities multi-select, a free-text "describe your ideal customer in your own words"
       box (stored in ideal_customer_text), allowed offers text, max discount slider.
   (5) Agent behaviour: first-touch mode explained in plain words ("I send the first message myself with one tap"
       = assisted, preselected and recommended, vs "The agent sends approved WhatsApp templates" = api_template,
       with a short warning that WhatsApp forbids cold messages and charges per template); autonomy mode explained in
       plain words (Approve every message / Approve only the first message / Full autopilot) with approve_all
       preselected; daily send cap; quiet hours; working days; demo mode
       switch (ON by default) + the whitelist phones input with an explanation of what demo mode does.
   Finish → set onboarding_completed=true and route to /icp with a toast "Now let's build your ideal customer
   profile". Redirect logged-in users with onboarding_completed=false to /onboarding (put the check in a small
   client hook — D owns the layout file; coordinate with D for one line in it).
4. /settings with tabs Business · Agent · Knowledge (reuse the same form sections as components so the wizard and
   settings share code). D adds the Channels tab later (P3-2 is yours, but the tab container is here — leave an
   empty "Channels" tab slot that renders <ChannelsSettings/> from components/channels when it exists).
5. RTL-safe inputs (dir="auto"), helpful hints under every field, and empty states. Component tests for the wizard
   navigation and validation.

Run poe check and npm run check.
~~~
**Definition of done:** a new user lands in the wizard, completes it in under 5 minutes, and every value persists.
**Self-check before you push:** do the wizard as a "non-technical owner" and list every confusing word.

---

## P2-2 · Normalization, dedupe, sourcing orchestration, daily cycle — Thu Nov 19 → Mon Nov 23
**Files you own:** `backend/app/core/phones.py`, `backend/app/services/leads_ingest.py`, `backend/app/workers/jobs/sourcing.py` (orchestration; C provides the query generation + search functions), `backend/app/workers/jobs/daily.py`, `backend/app/api/runs_trigger.py` (POST /runs/sourcing), tests.

~~~text
Read CLAUDE.md, docs/ARCHITECTURE.md §3 and docs/CONTRACTS.md (§3 leads/search_queries, §5 phones, §7 PlaceResult,
§10 jobs) first. C is building in parallel: app/agents/query_generator.py (generate_queries) and
app/adapters/search/google_places.py. Code against the contract; use the mock search source until C merges.

1. app/core/phones.py: normalize_eg_phone(raw) -> E.164 or None and is_eg_mobile(e164), using the phonenumbers
   library (region "EG"). Handle: "010 1234 5678", "+20 10…", "0020…", "201…", Arabic-Indic digits, landlines
   ("02 2345 6789", "03 …"), garbage. Mobile = +20 followed by 10/11/12/15 and 8 more digits. Exhaustive tests.
2. app/services/leads_ingest.py:
   - dedupe_key(place: PlaceResult) — priority: f"{source}:{source_ref}" if source_ref; else normalized mobile;
     else registrable domain; else normalized name + governorate (Arabic normalization as in the knowledge search:
     diacritics removed, hamza forms of alef → bare alef, taa marbuta → haa, alef maqsura → yaa,
     lowercased, punctuation stripped).
   - async def ingest_places(session, run, tenant_id, places, icp_version_id) -> IngestResult(created, duplicates):
     for each PlaceResult, compute the dedupe key; skip if a lead with the same key exists for the tenant (also check
     a secondary key: the same normalized mobile on another lead → duplicate); otherwise create the lead with
     status=new, domain extracted from the website, city/governorate, raw, sourcing_run_id. Skip business_status
     CLOSED_PERMANENTLY (count as skipped). Bulk-friendly (no N+1 queries: preload the existing keys for the tenant).
3. app/workers/jobs/sourcing.py — job_run_sourcing(ctx, tenant_id, max_results=60):
   inside agent_run(kind=SOURCING): load the active ICP (if none → fail the run with a clear error
   "no_active_icp"); call C's generate_queries(run, icp, profile) → QueryPlan; for each query call
   registry.get_search_source().search(query, region, max_results=20), store a search_queries row, ingest; stop
   once max_results new leads were created; record a DECISION step with totals; then enqueue
   job_score_leads(tenant_id, run_id). One failing query must not kill the run.
4. app/api/runs_trigger.py — POST /api/v1/runs/sourcing {max_results?} → {run_id}: 409 if a sourcing run is
   already running for this tenant, 400 if onboarding is incomplete or there is no active ICP. Create the run row
   with tracing.create_queued_run(...) and pass run_id into the job, which opens agent_run(..., run_id=run_id)
   (CONTRACTS §5), so the UI can show the run immediately.
5. app/workers/jobs/daily.py — job_daily_cycle: cron at 09:00 Africa/Cairo on working days: for every tenant with
   agent_enabled and onboarding_completed, enqueue job_run_sourcing(tenant_id, daily_new_leads_target).
6. Tests: phones, dedupe (same place twice; same mobile under two place ids; Arabic name variants), ingest with no
   N+1 queries (assert the query count), the job end to end with the mock search source and mock LLM, the 409/400
   paths, and tenant isolation.

Run poe check.
~~~
**Definition of done:** "Run agent now" → a run → new leads with no duplicates across two runs → scoring is enqueued.
**Self-check before you push:** run sourcing twice with a real Places key and count duplicates in SQL.

---

## P3-2 · WhatsApp channel: adapter, webhook, sending, demo routing, settings UI — Tue Nov 24 → Mon Nov 30
**Critical path:** on **Day 1 of P3**, merge `services/messaging.py` with the contract signatures working against the mock channel, so C (outreach) and D (reply agent) are unblocked. Then build the real adapter.
**Files you own:** `backend/app/adapters/channels/*`, `backend/app/services/messaging.py`, `backend/app/api/channels.py`, `backend/app/api/webhooks_whatsapp.py`, `backend/app/workers/jobs/messaging.py` (job_send_message + a stub job_handle_inbound that D replaces), `frontend/src/components/channels/*`, `docs/setup-whatsapp.md` (C wrote a first version in P0-3; you extend it), tests.

~~~text
Read CLAUDE.md, docs/ARCHITECTURE.md §7 and docs/CONTRACTS.md (§3 channel_connections, message_templates,
conversations, messages, demo_routes; §7 ChannelAdapter, InboundMessage, StatusUpdate; §9 messaging; §10
job_send_message / job_handle_inbound; §12 demo routing) first. Use the official WhatsApp Cloud API (Meta Graph API)
only — never unofficial WhatsApp Web libraries. If unsure about any Graph API detail, read Meta's current docs instead
of guessing; the Graph API version comes from settings.WHATSAPP_GRAPH_VERSION.

STEP 1 (merge first, same day): app/services/messaging.py with create_outbound, approve_message, reject_message,
send_message, resolve_demo_target, mark_sent_manually, build_wa_link and assistant_link exactly as in the contract
(kind=ASSISTED messages get status awaiting_manual_send and are never enqueued; in demo mode build_wa_link uses
the whitelisted phone), working against the mock channel; job_send_message;
a stub job_handle_inbound(ctx, message_id) that only logs (D replaces it in P3-4). Tests. Push it immediately.

STEP 2: the real adapter — adapters/channels/whatsapp_cloud.py (WhatsAppCloudAdapter: ChannelAdapter):
- send_template(to, template_name, language, params): POST /{phone_number_id}/messages with type=template and a body
  component with text parameters. Template params must not contain newlines/tabs or more than 4 consecutive
  spaces — sanitise them and log when you do.
- send_text(to, body): type=text (valid only inside the 24h customer-service window — the caller checks; you map
  Meta's error for an expired window to a clear SendResult.error="window_closed").
- check_connection(): GET the phone number object; return (ok, display_phone_number or the error).
- list_templates(): GET /{waba_id}/message_templates → TemplateInfo (count the {{n}} params).
- Map Meta error codes to readable errors (invalid token, rate limit, recipient not in the allowed list for test
  numbers, template not approved, re-engagement / window closed). Retries with backoff for 5xx/429 only.
- registry.get_channel(session, tenant_id, WHATSAPP) loads channel_connections, decrypts the secrets, returns the
  adapter (the mock when USE_MOCK_ADAPTERS).

STEP 3: send_message(message_id) details:
- Reload the message+lead+settings; refuse (status=blocked, error) if the lead is opted_out, or if the tenant's
  outbound sent today ≥ daily_send_cap (purpose FIRST_TOUCH/FOLLOWUP only; replies are not capped), or if it is
  outside quiet hours for FIRST_TOUCH/FOLLOWUP (then leave it queued and set next_action_at to the next allowed time).
- Target number: if settings.demo_mode → resolve_demo_target (CONTRACTS §12), store redirected_to; else the lead's
  primary MOBILE contact.
- kind=TEMPLATE → send_template; kind=TEXT → require conversation.window_expires_at > now, else status=failed
  error=window_closed.
- On success: status=sent, provider_message_id, sent_at; update lead.last_outbound_at / first_contacted_at; get or
  create the conversation; then call outreach.on_message_sent(session, message) (C's hook from P3-3, which moves
  the lead QUEUED→CONTACTED; until C merges, guard the import and leave a TODO). Record an EXTERNAL_API trace step (no message body, no phone in the trace — mask it).

STEP 4: webhook — app/api/webhooks_whatsapp.py:
- GET: hub.mode=subscribe + hub.verify_token == settings.WHATSAPP_VERIFY_TOKEN → return hub.challenge as plain text.
- POST: verify X-Hub-Signature-256 (HMAC-SHA256 of the raw body with WHATSAPP_APP_SECRET; constant-time compare;
  401 if invalid). Parse it into InboundMessage/StatusUpdate (put the parser in the adapter module). Route by
  metadata.phone_number_id → channel_connections → tenant. Respond 200 fast; process idempotently
  (provider_message_id unique).
- Status updates → update messages.status (never downgrade read→delivered); failed → error text.
- Inbound text: find the lead (demo_routes for whitelisted phones when demo_mode, else contacts.value = from_phone,
  else a "#<ref_code>" in the text → the lead-initiated rule in CONTRACTS §12: add the number as a MOBILE contact
  with source "lead_initiated" and continue); unknown sender with no valid code → store a notification
  "message from unknown number" and stop. Save the message (direction=inbound,
  author=LEAD, status=received), set conversation.window_expires_at = timestamp + 24h, lead.last_inbound_at, and
  transition the lead to REPLIED when allowed. Detect STOP words immediately (stop, unsubscribe, and the common Egyptian Arabic ways
  to say "cancel" and "stop sending" — keep the list in one constant): transition OPTED_OUT before anything else. Then enqueue
  job_handle_inbound(message_id). Non-text messages (image/voice/location) → store with body "[image]" etc. and
  still enqueue.

STEP 5: API + UI.
- GET /channels; PUT /channels/whatsapp {phone_number_id, waba_id, access_token} → encrypt the secrets, run
  check_connection, save the status; POST /channels/whatsapp/test {to} → send the "hello_world" template (or the
  first approved template); POST /channels/whatsapp/templates/sync → upsert message_templates and let the owner tag
  the purpose intro/followup.
- frontend components/channels/ChannelsSettings.tsx (rendered in B's own Settings "Channels" tab): a guided, step-by-
  step "Connect WhatsApp" card written for non-technical owners (links to Meta, screenshots placeholders, where to
  find each id), connection status, test-send box, the templates table with a purpose dropdown, and the demo-mode
  reminder. Show the webhook URL to paste into Meta: {PUBLIC_BASE_URL}/api/v1/webhooks/whatsapp.
- docs/setup-whatsapp.md: the developer steps (Meta app, test number, adding up to 5 recipient phones, templates,
  webhook with cloudflared, subscribing to the messages field).

Tests: signature verification (valid/invalid), the webhook verify handshake, idempotency, status ordering, demo
routing round-trip (send to lead X → redirected to test phone → an inbound from the test phone maps back to X), opt-out
words, daily cap, quiet hours, window_closed, tenant routing by phone_number_id. Use respx for Graph API calls.
Run poe check and npm run check.
~~~
**Definition of done:** from the UI, a team member connects the test number, sends a test template to their phone, replies, and sees the reply stored against the right lead. A message from a new phone containing a lead's `#ref` code is attached to that lead.
**Self-check before you push:** do the whole connect → send → reply loop on your own phone; try an invalid token.

---

## P4-4 · Feedback loop + demo seed + end-to-end smoke test ⭐ SHOWCASE — Tue Dec 1 → Sun Dec 6
**Why it matters for the discussion:** "the system gets smarter over time". Show the insights generated from won/lost deals and a re-scoring that changes because of them.
**Files you own:** `backend/app/agents/feedback.py`, `backend/app/agents/prompts/feedback.md`, `backend/app/services/insights.py` (replace A's stub), `backend/app/workers/jobs/feedback.py`, `backend/app/api/insights.py` (GET/POST, see below), `backend/scripts/seed_demo.py`, `backend/tests/e2e/*`, `docs/DEMO-SCRIPT.md`, `frontend/src/components/insights/*`.

~~~text
Read CLAUDE.md, docs/ARCHITECTURE.md and docs/CONTRACTS.md (§3 lead_outcomes, learned_insights; §9 insights;
§10 job_feedback) first.

Part 1 — closed feedback loop.
1. job_feedback(ctx, tenant_id) inside agent_run(kind=FEEDBACK): requires ≥ 3 outcomes (otherwise finish with
   output_summary {skipped:"not_enough_outcomes"}). Compute stats in SQL/Python (not the LLM): win rate by category,
   governorate, score band (0–3/4–6/7–8/9–10), rating band, reviews band, presence of a website; reply rates by the
   same segments; the average time to reply for won vs lost.
2. agents/feedback.py (PROMPT_VERSION "feedback@1"): llm_structured tier=SMART effort="medium", input = the stats +
   10 short won/lost lead summaries (no phone numbers) + the current ICP; output = LearnedInsights {insights:
   list[str] (3–7 actionable rules phrased for the scorer, e.g. "Shops in Nasr City with >50 reviews converted 3×
   more — score them higher"), icp_suggestions: list[str], caveats: list[str]} — tell the model to be cautious with
   small samples and to cite the numbers.
3. Save as a new learned_insights version (is_active=true, previous ones inactive; stats stored too). Trigger:
   automatically after every 3rd new outcome (hook into POST /leads/{id}/outcome via an enqueue — coordinate one line
   with A), plus a button.
4. GET /api/v1/insights (active + history), POST /api/v1/insights/run, POST /api/v1/insights/{id}/deactivate
   (the owner stays in control). A's scorer already reads get_active_insights — implement it properly here.
5. frontend components/insights/InsightsCard.tsx: shows the active insights, the stats table, "Re-run", and
   "Disable"; C will place it on the Reports page (coordinate) — also export a compact version for the dashboard.

Part 2 — demo seed (scripts/seed_demo.py, poe task seed-demo; idempotent; --reset flag). The demo tenant uses
first_touch_mode=api_template (so the live demo shows the full automatic loop on the team phones) and also has ~5
assisted messages waiting in /outreach → "To send" to show the safe default:
6. Create the demo tenant "Little Stars Kids Wear" (fictional kids-clothing factory, 10th of Ramadan) with an owner
   login demo@example.com / a password printed to the console, full settings, a knowledge .md file (write a realistic
   Arabic+English company profile: products, prices, minimum orders, offers up to 10%), an active ICP, ~80 fictional
   leads across Cairo/Giza with realistic Arabic names and statuses spread across the whole funnel, contacts,
   conversations in Egyptian Arabic for ~25 of them (including each reply intent), 6 won and 4 lost outcomes with
   values, agent_runs with steps, tokens and costs spread over the last 21 days (so the reports look alive), and one
   learned_insights version. Use only fictional names and fake +20 numbers in the 0100000xxxx range — never real
   businesses or numbers.

Part 3 — end-to-end smoke test + demo script:
7. tests/e2e/test_full_cycle.py (mock adapters + mock LLM fixtures): register → settings → knowledge → ICP →
   sourcing → scoring → enrichment → outreach tick → approve → send → simulate an inbound "interested, send me the prices"
   (written in Egyptian Arabic) →
   classification → reply → notification → mark won → feedback job. It must run in CI.
8. docs/DEMO-SCRIPT.md: a 7-minute live demo script (clicks + what to say), mapped to the 9 showcase points in
   00-START-HERE §5, with a fallback plan (recorded video/screenshots) if Wi-Fi or Meta fails during the
   presentation.

Run poe check and npm run check.
~~~
**Definition of done:** `poe seed-demo` gives a beautiful, believable demo account; the e2e test passes in CI; feedback insights appear and change the scoring prompt.
**Self-check before you push:** log into the demo account cold and walk through DEMO-SCRIPT.md exactly as written.
