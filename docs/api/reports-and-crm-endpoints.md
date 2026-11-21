# Reports & CRM endpoints (for D's pages)

All under `/api/v1`, cookie auth, tenant-scoped, errors as `{"error": {"code", "message"}}`.
Full shapes: the Pydantic models in `backend/app/services/reports.py` and `backend/app/services/crm.py`
(also in `/docs` when the API runs).

## Reports (P4-3) — page `/reports`

`from`/`to` = `YYYY-MM-DD` (Cairo days, inclusive). Default: last 30 days. 422 `invalid_range` / `range_too_long`.

| Route | Returns |
|---|---|
| GET `/reports/summary?from&to` | `kpis: {name: {value, previous, delta, definition}}` + `previous_from/to`, `cost_is_estimated` |
| GET `/reports/funnel?from&to` | `stages: [{stage, count, rate_from_previous}]` (sourced → qualified → contacted → replied → positive → won) |
| GET `/reports/segments?by=governorate\|category\|score_band` | `rows: [{segment, contacted, replied, positive, won, reply_rate, positive_reply_rate}]` |
| GET `/reports/costs?from&to` | `total_cost_usd`, `cost_per_qualified_lead_usd`, `cost_per_positive_reply_usd`, `cache_hit_ratio`, `by_kind[]`, `daily[]` (day, kind), `models[]` |
| GET `/reports/timeseries?metric=sourced\|contacted\|replies\|won` | `points: [{day, value}]`, one per day, zero-filled |

KPI names: sourced, scored, qualified, qualified_rate, contactable_rate, contacted, replied, reply_rate, positive,
positive_reply_rate, lead_response_minutes, our_response_minutes_agent, our_response_minutes_human, won, lost,
win_rate, pipeline_value_egp, llm_cost_usd, cost_per_qualified_lead_usd, cost_per_positive_reply_usd,
cache_hit_ratio. Rates are 0..1 (or `null` when the denominator is 0). Use each KPI's `definition` as its tooltip.

## CRM (P4-1) — pages `/pipeline`, `/leads/[id]`, export button on `/leads`

| Route | Notes |
|---|---|
| GET `/leads/{id}` | lead fields + `contacts[]`, `messages[]` (chronological), `history[]`, `notes[]` (newest first), `outcome`, `window_expires_at` |
| PATCH `/leads/{id}` `{status?, agent_paused?}` | returns the detail; 409 `opted_out` for an opted-out lead |
| POST `/leads/{id}/notes` `{body}` | 201 note |
| POST `/leads/{id}/outcome` `{outcome: won\|lost, value_egp?, reason?}` | 201; lead → won/lost, agent paused; again = replaces |
| POST `/leads/{id}/contacts` `{type, value}` | 201; 422 `invalid_phone` / `not_a_mobile`; 409 `contact_exists` |
| POST `/leads/{id}/messages` `{body}` | 201 (queued); 409 `window_closed` → show "a template is required"; 409 `opted_out` |
| GET `/leads/export.xlsx?status&min_score&q&governorate&sourcing_run_id` | Excel file (same filters as the list) |

Kanban drag → PATCH `{status}`; dropping on Won/Lost → open the outcome dialog → POST `/outcome`. Disable the composer
when `window_expires_at` is null or in the past.
