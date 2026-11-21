# Service modules

## Knowledge

`app.services.knowledge` provides tenant-scoped company knowledge retrieval:

- `get_knowledge_text(session, tenant_id, max_chars=120_000)` concatenates ready files in created-at
  order without cutting complete file blocks.
- `search_knowledge(session, tenant_id, query, k=5)` returns ranked keyword matches prefixed by filename.
- `extract_knowledge_text(...)` extracts and normalizes PDF, DOCX, Markdown and text files.

The API stores files under `UPLOAD_DIR/<tenant_id>/` and never exposes raw extraction exceptions or
filesystem paths. Upload/database failures are logged server-side and returned as safe contract error codes.

## Reports (P4-3)

`app.services.reports`: tenant-scoped SQL aggregates for `/reports/*` (summary with the previous equal-length period,
funnel, segments, costs, timeseries). Ranges are Cairo calendar days, both inclusive (default: the last 30 days).
Every metric's definition is in the module docstring and in `METRIC_DEFINITIONS` (sent with each KPI so the UI can
show it as a tooltip). AI cost is an estimate at the paid list price (`cost_is_estimated: true`).

## CRM (P4-1)

`app.services.crm`: lead detail, status/pause changes (through `lead_state.transition`, actor `user`), notes,
won/lost outcomes (pauses the agent, then `insights.on_outcome_recorded` after the commit), manual contacts
(phones normalized to E.164; a mobile unblocks a `no_contact` lead), manual WhatsApp text (409 `window_closed`
outside the 24h window) and the Excel export. Opted-out leads cannot be moved or messaged from here.
