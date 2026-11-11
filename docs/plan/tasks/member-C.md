# Member C — Task Prompts

**Your tasks:** P0-3 LLM layer & tracing ⭐ · P1-3 ICP builder agent ⭐ · P2-1 Query generator + Google Places · P3-3 Outreach engine & approvals ⭐ · P4-3 Reports & cost ⭐
**You are buddy for:** B in P0 · A in P1 · D in P2 · B in P3 · A in P4
**Change from the first version:** the Day-1 external setup and the adapter layer moved to A, so your P0 task is the LLM wrapper and tracing only.
**Before every task:** read `00-START-HERE.md` §4. Paste only the part between the `~~~text` fences into Claude Code, **in plan mode**, from the repo root.

---

## P0-3 · LLM wrapper, pricing, tracing & runs API ⭐ SHOWCASE — Wed Nov 11 → Fri Nov 13
**Buddy:** D.
**Why it matters for the discussion:** this is the backbone of two showcases. *Tracing* makes every agent step visible,
and *model routing + caching* is the cost story.
**Files you own:** `backend/app/agents/llm.py`, `backend/app/agents/pricing.py`, `backend/app/core/tracing.py`, `backend/app/api/runs.py` (GET /runs, GET /runs/{id}), `backend/tests/fixtures/llm/`, `backend/app/agents/README.md`, tests.

~~~text
Read CLAUDE.md, docs/ARCHITECTURE.md and docs/CONTRACTS.md (§5 tracing, §6 LLM layer) completely.
Use the claude-api skill for all Anthropic SDK code — do not guess SDK signatures. The model IDs come from
settings.MODEL_SMART ("claude-opus-5-5") and settings.MODEL_FAST ("claude-haiku-5-5").

Build the layer that every agent task depends on. The other 3 teammates start using it on Saturday, so the
signatures must match CONTRACTS.md exactly. (A is building the adapter layer in parallel; you don't need it.)

1. app/core/tracing.py: RunContext, agent_run(...) and create_queued_run(...) exactly as in CONTRACTS §5. Trace
   writes use their own short DB session/transaction so traces survive even when the job's main transaction rolls
   back. Errors inside the context mark the run failed, store the error text, record an ERROR step, and re-raise.
   Aggregate tokens and cost on exit. Steps must truncate big payloads (max 20 KB of JSON per field) and mask phone
   numbers (keep the last 3 digits).
2. app/agents/pricing.py: a price table (USD per 1M tokens: input, output, cache_read, cache_write) for
   claude-opus-5-5 and claude-haiku-5-5. Take every price from the claude-api skill or the Anthropic pricing page
   (don't trust numbers from memory) and leave a comment with the date and source. cost_usd(model, usage).
3. app/agents/llm.py: llm_structured and llm_tool_loop exactly as in CONTRACTS §6, using the official anthropic
   AsyncAnthropic client (one module-level client):
   - tier → model id from settings; always set output_config effort explicitly; never send temperature/top_p/top_k;
     no assistant prefill; thinking is adaptive (Opus 5.5 cannot disable it).
   - llm_structured: structured outputs via client.messages.parse with the Pydantic output_model.
     System prompt + cached_context go in the system blocks with a cache_control breakpoint after cached_context; the
     user text comes after it.
   - llm_tool_loop: a manual loop (so we can trace each turn): tools built from ToolSpec (JSON schema from the
     Pydantic input_model, strict: true, additionalProperties false), tool_choice auto, execute the tool calls (in
     parallel if several), return all tool_result blocks in one user message, is_error results for exceptions, stop
     at end_turn or max_iterations. Validate each tool input with the Pydantic model before calling the handler.
   - Check stop_reason on every response: "refusal" → raise LLMRefused (and record it); "max_tokens" → raise
     LLMOutputTruncated. Enable the server-side refusal fallback for the Opus model as the claude-api skill
     recommends, and say in your summary what you enabled.
   - Retry rate-limit/overloaded/5xx/connection errors with exponential backoff (max 3), never 400s.
   - Record one LLM_CALL step per model call: model, tokens incl. cache_read_input_tokens, cost, latency, lead_id,
     the input (system prompt name + PROMPT_VERSION + the user text, truncated) and the output.
   - Mock mode (settings.USE_MOCK_LLM): as described in CONTRACTS §6 (fixture file by name, else polyfactory with a
     seed derived from name). Still record a step with model "mock" and zero cost.
4. app/api/runs.py: GET /api/v1/runs?kind=&status=&page= (list) and GET /api/v1/runs/{id} (run + ordered steps).
   Tenant-scoped. The router is auto-mounted: just expose `router` in the module.
5. Tests: tracing (success, failure, truncation, phone masking, survives a rollback), llm wrapper with the Anthropic
   HTTP layer mocked by respx (structured output parsed, refusal raises, max_tokens raises, retry on 529/429, no retry
   on 400, the cache_control placement in the request body, the tool loop with 2 tool calls in one turn), the mock
   mode, the runs API + tenant isolation.

Finally write backend/app/agents/README.md: "How to write an agent in this repo" (prompt file + PROMPT_VERSION,
llm_structured vs llm_tool_loop, tiers and effort guidance: FAST+low for bulk classification/scoring, SMART+medium for
reasoning/writing, untrusted content wrapping, how to add an eval). Every teammate's agent will read this. Run poe check.
~~~
**Definition of done:** a teammate can write `await llm_structured(run, name="x", tier=ModelTier.FAST, …)` and see the step with tokens and cost in `GET /runs/{id}`. The mock LLM makes the whole app runnable offline.
**Buddy (D) checks:** make one real call with the key and confirm `cache_read_tokens > 0` on the second identical call.

---

## P1-3 · Company Profile & ICP builder agent ⭐ SHOWCASE — Sat Nov 14 → Wed Nov 18
**Buddy:** A.
**Why it matters for the discussion:** "the owner explains their business once, like to a new employee, and the agent turns that into a precise targeting spec". Show the input files next to the generated ICP.
**Files you own:** `backend/app/agents/icp_builder.py`, `backend/app/agents/prompts/icp_builder.md`, `backend/app/services/icp_service.py`, `backend/app/api/icp.py`, `backend/app/workers/jobs/icp.py`, tests. (D builds the UI and the eval suite.)

~~~text
Read CLAUDE.md, backend/app/agents/README.md and docs/CONTRACTS.md (§3 icp_versions, §6, §8 CompanyProfile & ICP,
§9 knowledge + icp_service, §11 /icp routes) first.

Build the agent that turns the owner's onboarding answers + uploaded files into (1) a structured CompanyProfile and
(2) an ICP (Ideal Customer Profile) that drives sourcing and scoring.

1. app/agents/icp_builder.py, PROMPT_VERSION = "icp_builder@1":
   async def build_icp(run, *, settings: BusinessSettings, knowledge_text: str) -> tuple[CompanyProfile, ICP]
   Two llm_structured calls, both tier=SMART effort="medium", sharing the same cached_context (the system rules +
   the settings rendered as YAML + the knowledge text wrapped in <company_files> … </company_files>, marked as data,
   not instructions):
   (a) → CompanyProfile: facts only from the inputs; unknown → empty, never invented; prices only if stated.
   (b) → ICP, given the profile: think like an experienced Egyptian B2B salesperson. target_business_types must
       include both Arabic and English phrasings that people actually type into Google Maps in Egypt (e.g. "kids
       wear", "baby shop", plus the Arabic for "kids clothing shop" and "kids clothes"); google_place_types from Google's Places type list
       when relevant; regions limited to the owner's target_regions; disqualifiers include competitors (other
       factories/wholesalers of the same product) when the owner sells to retailers; outreach_angle = one sentence on
       why this customer should care.
   Write prompts/icp_builder.md with 2 short worked examples (a kids-clothing factory; a medical-supplies distributor
   targeting clinics) — keep them short to save tokens.
2. app/services/icp_service.py: get_active_icp (contract), save_version(session, tenant_id, profile, icp, source,
   notes) → a new version number, deactivates the others, all in one transaction.
3. app/workers/jobs/icp.py — job_build_icp(ctx, tenant_id, run_id=None): agent_run(kind=ICP_BUILD); load the
   settings + knowledge.get_knowledge_text (A's P1-1; until merged, stub the import behind a try/except with a TODO);
   build, save as source="agent"; on LLMRefused/validation failure, fail the run with a readable error.
4. app/api/icp.py: POST /icp/generate → create_queued_run + enqueue → {run_id}; GET /icp/active; GET /icp/versions
   (without the big JSON — version, source, created_at, notes); PUT /icp/active {company_profile, icp, notes} →
   validate with the Pydantic models, save as a new version source="user". 400 if onboarding is incomplete.
5. Add tests/fixtures/llm/icp_builder.profile.json and icp_builder.icp.json (realistic, for the kids-clothing
   fixture business) so the mock LLM returns believable data for the UI and the other teammates.
6. Tests: the job with the mock LLM, versioning (activate/deactivate), the PUT validation errors, tenant isolation,
   and a test that the knowledge text is inside the cached_context (not the user part) — inspect the call via a spy.

Run poe check. Then generate an ICP for real (ask the human first; it costs a few cents) from the demo business
files and paste the JSON in your summary for the team to review.
~~~
**Definition of done:** "Generate ICP" produces a sensible profile + ICP in about 30–60 s, saved as v1. Editing creates v2.
**Buddy (A) checks:** run it on two very different businesses; is anything invented that is not in the files?

---

## P2-1 · Query generator + Google Places adapter — Thu Nov 19 → Sat Nov 21
**Buddy:** B (B orchestrates the sourcing job and calls your two functions).
**Files you own:** `backend/app/agents/query_generator.py`, `backend/app/agents/prompts/query_generator.md`, `backend/app/adapters/search/google_places.py`, `backend/app/core/geo_eg_coords.py`, tests.

~~~text
Read CLAUDE.md, backend/app/agents/README.md and docs/CONTRACTS.md (§7 SearchSource/PlaceResult/RegionFilter,
§8 QueryPlan) first. B is writing the sourcing job that calls your functions in parallel; keep the signatures exact.

1. app/agents/query_generator.py, PROMPT_VERSION "query_generator@1":
   async def generate_queries(run, *, icp: ICP, profile: CompanyProfile, already_used: list[str]) -> QueryPlan
   tier=FAST, effort="low". 5–15 queries in the language people use on Google Maps in Egypt (mostly Arabic, plus
   English variants), one region per query, spread across all the target regions/cities, avoiding queries in
   already_used (pass the last 100 queries from search_queries for the tenant — add a small helper for that).
   Post-process: dedupe the normalized queries, drop the ones outside the ICP regions.
2. app/adapters/search/google_places.py — GooglePlacesSource (name "google_places") using Places API (New)
   Text Search (POST https://places.googleapis.com/v1/places:searchText) with httpx:
   - headers X-Goog-Api-Key and an X-Goog-FieldMask limited to what we store (id, displayName, formattedAddress,
     addressComponents, location, types, primaryTypeDisplayName, nationalPhoneNumber, internationalPhoneNumber,
     websiteUri, googleMapsUri, rating, userRatingCount, businessStatus) — field masks drive the price, so request
     nothing else; double-check the field names against Google's current docs.
   - languageCode "ar", regionCode "EG", a locationBias circle from app/core/geo_eg_coords.py (center lat/lng +
     radius for each governorate and the main cities — create this constant).
   - Pagination with nextPageToken up to max_results (the API caps a query at 60).
   - Map to PlaceResult (governorate/city from addressComponents when present, else from the RegionFilter).
   - Errors: 403/400 → a clear exception message (key restrictions / API not enabled); 429/5xx → retry with backoff.
   - Record nothing here (no RunContext in adapters); B's job records the EXTERNAL_API step around your call. Instead
     return the number of billable requests made via an attribute last_request_count so the job can log it.
   Register it in the registry.
3. Tests: the query post-processing; the Places adapter with respx (pagination, the field mask header present,
   Arabic display names, missing phone/website, error mapping).
4. A manual script backend/scripts/try_places.py "kids clothing shop" --governorate Cairo (also try the Arabic phrasing) that prints 20 results (for the
   team to sanity-check the key and the data).

Run poe check and paste the output of try_places.py (names only) into your summary.
~~~
**Definition of done:** with a real key, `try_places.py` returns relevant Cairo kids-clothing shops; the generated queries look like what a salesperson would type.
**Buddy (B) checks:** run the full sourcing job with your adapter and count relevant vs. irrelevant results by eye.

---

## P3-3 · Outreach engine, personalization, autonomy & approval queue ⭐ SHOWCASE — Tue Nov 24 → Mon Nov 30
**Buddy:** D.
**Why it matters for the discussion:** *human-in-the-loop autonomy levels*. The owner chooses how much to trust the agent, and the approval queue shows the AI-written message plus its rationale before anything is sent.
**Files you own:** `backend/app/services/autonomy.py`, `backend/app/services/outreach.py`, `backend/app/agents/message_personalizer.py`, `backend/app/agents/prompts/message_personalizer.md`, `backend/app/workers/jobs/outreach.py`, `backend/app/api/outreach.py`, `frontend/src/app/(app)/outreach/*`, `frontend/src/components/outreach/*`, tests.
**Depends on:** B's `services/messaging.py` (merged on Day 1 of P3; until then code against the contract).

~~~text
Read CLAUDE.md, backend/app/agents/README.md, docs/ARCHITECTURE.md §3–4 and docs/CONTRACTS.md (§3
business_settings.sequence_steps, leads.sequence_step/next_action_at/agent_paused, message_templates; §8
PersonalizedOpening; §9 messaging + autonomy; §10 job_outreach_tick; §11 /outreach routes) first.

Build the engine that decides who gets messaged, when, and with what — WhatsApp templates only for first touch and
follow-ups (the 24h-window conversation is D's reply agent).

1. services/autonomy.py — needs_approval(settings, purpose) exactly as in the contract.
2. agents/message_personalizer.py, PROMPT_VERSION "message_personalizer@1":
   async def personalize(run, *, profile, icp, lead, template: MessageTemplate, step_purpose) -> PersonalizedOpening
   tier=FAST effort="low"; the cached_context is the profile + ICP + the template body with {{n}} placeholders;
   the user part is the lead data (wrapped as untrusted <lead> data). The params must make the template read
   naturally in Egyptian Arabic, mention something specific and true about the lead (its area, category or rating —
   only from the data), contain no newlines/tabs, be ≤ 60 chars each, contain no prices or discounts, and make no
   claims we can't support. Validate: the param count equals template.param_count, else retry once, else fall back to
   safe generic params (business name + area).
3. services/outreach.py + workers/jobs/outreach.py — job_outreach_tick (cron every 5 minutes):
   for each tenant with agent_enabled: skip if outside working days/quiet hours (Africa/Cairo); compute the
   remaining daily cap (sent today with purpose first_touch/followup); select due leads
   (next_action_at <= now, agent_paused=false, status in {enriched, contacted, later}, not opted_out), oldest first,
   limited by the remaining cap; per lead decide the step from settings.sequence_steps and lead.sequence_step:
   - enriched → first_touch with the template whose purpose is intro → transition ENRICHED→QUEUED;
   - contacted with no inbound since the last outbound and the next step due → followup;
   - later → when due, a followup template (transition LATER→CONTACTED after the send);
   - no steps left → clear next_action_at (the sequence is finished).
   Create the message via messaging.create_outbound(kind=TEMPLATE, template_name, template_params, body=rendered
   preview, needs_approval=needs_approval(settings, purpose)); bump sequence_step; set next_action_at for the next
   step (day_offset difference); make sure the same lead never gets two messages from one tick (row lock / SKIP
   LOCKED). If no approved template with the needed purpose exists → notify the owner once ("channel_error") and
   skip. One agent_run(kind=OUTREACH_TICK) per tenant per tick only when there was work (don't spam empty runs).
   When a first-touch message becomes sent, the lead must move QUEUED→CONTACTED — B's send_message updates the
   message status; add the transition in a small hook function outreach.on_message_sent(session, message) and ask B
   to call it (one line, agree in the PR).
4. api/outreach.py: GET /outreach/queue (pending_approval messages with lead info, the personalization rationale and
   the template preview), POST /outreach/messages/{id}/approve {params?} (the edited params are validated like
   above) → messaging.approve_message, POST /outreach/messages/{id}/reject → messaging.reject_message + transition
   QUEUED→ENRICHED with agent_paused=true (the owner decided not to contact this lead now). Bulk approve
   endpoint: POST /outreach/approve-bulk {ids}.
5. Frontend /outreach: the approval queue — cards showing the lead (name, area, score, reasons), the rendered
   WhatsApp preview bubble (dir="auto"), the "why this message" rationale, editable params with live preview and
   character counters, Approve / Reject, select-all + bulk approve, an empty state explaining the autonomy modes
   with a link to settings, and a counter badge in the sidebar (expose a hook usePendingApprovals; D owns the
   sidebar, so ask D to render it).
6. Tests: needs_approval for all modes; the tick selection (quiet hours, working days, cap, paused, opted_out,
   later due), sequence progression over simulated days (freeze the time), no double-send under two concurrent ticks,
   the missing template path, approve with edited params, reject transitions; component tests for param editing.

Run poe check and npm run check.
~~~
**Definition of done:** with the autonomy mode `approve_all`, enriched leads show up in the queue with good Arabic previews. Approving sends them (to the demo phones). Follow-ups happen on schedule.
**Buddy (D) checks:** approve 3 messages and receive them on your phone; switch to autopilot and confirm the cap and quiet hours are respected.

---

## P4-3 · Reports & cost analytics ⭐ SHOWCASE — Tue Dec 1 → Sat Dec 5
**Buddy:** A.
**Why it matters for the discussion:** this replaces Metabase. Above all it shows **cost per qualified lead** and **cost per positive reply** (the agentic-engineering economics), next to the business funnel.
**Files you own:** `backend/app/api/reports.py`, `backend/app/services/reports.py`, `frontend/src/app/(app)/reports/*`, `frontend/src/components/reports/*`, tests.

~~~text
Read CLAUDE.md and docs/CONTRACTS.md (§3 all tables, §11 /reports routes) first. Read the dataviz skill before
writing any chart code.

Metric definitions (put them in services/reports.py docstrings and show them as tooltips in the UI):
- sourced = leads created in the range; scored = leads with a score; qualified rate = qualified-or-later / scored.
- contactable rate = leads that reached enriched / qualified.
- contacted = leads with first_contacted_at in the range.
- reply rate = contacted leads with ≥1 inbound message / contacted.
- positive reply rate = contacted leads whose status is (or passed through, per lead_status_history) interested,
  wants_offer, wants_management or won / contacted.
- lead response time = median minutes between our first outbound and their first inbound.
- our response time = median minutes between an inbound message and our next outbound (split agent vs human).
- win rate = won / (won + lost); pipeline value = the sum of value_egp for won.
- LLM cost = the sum of agent_runs.total_cost_usd in the range; cost per qualified lead; cost per positive reply;
  cost by run kind; tokens by model; cache hit ratio = cache_read_tokens / input tokens.
- Segments: governorate, category, score band (0–3, 4–6, 7–8, 9–10).

Backend: GET /reports/summary?from&to (KPIs + the same values for the previous equal-length period for deltas),
/reports/funnel, /reports/segments?by=…, /reports/costs (daily cost series by kind + the model/caching table), and
/reports/timeseries?metric=… for daily sourced/contacted/replies. Pure SQL aggregates (no Python loops over all leads),
tenant-scoped, default range = the last 30 days, Africa/Cairo day boundaries.

Frontend /reports: a date-range picker; a KPI row with deltas; the funnel (sourced → qualified → contacted → replied
→ positive → won); a reply-rate by segment bar chart with a segment switcher; response-time cards; an "AI cost" section
(cost per qualified lead, cost per positive reply, cost by run kind over time, cache hit ratio, a model usage table);
B's <InsightsCard/> placed at the bottom (import from components/insights; a placeholder until B merges). Each metric
has an info tooltip with its definition. Download CSV for each table.

Tests: seed a small known dataset in the test and assert every metric's exact value (including the medians and the
previous-period deltas), tenant isolation, and empty-range behaviour. Run poe check and npm run check.
~~~
**Definition of done:** on the demo seed, the reports page tells a clear story, and every number can be explained with its definition.
**Buddy (A) checks:** verify the reply rate and cost per qualified lead by hand with SQL.

---

## Your buddy duties (summary)
- **P0 → B** (data model): compare each table with CONTRACTS §3 column by column.
- **P1 → A** (knowledge upload): upload a scanned PDF and a big DOCX and see what happens.
- **P2 → D** (leads UI + activity): open a sourcing run in Agent Activity; can you follow what the agent did?
- **P3 → B** (WhatsApp): do the full connect → send → reply loop on your phone; try an invalid token.
- **P4 → A** (CRM): export with Arabic names and open it in Excel; drag cards; try a manual message outside the window.
