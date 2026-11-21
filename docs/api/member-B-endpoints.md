# Member B backend endpoints — handoff for the UI (D)

All routes are under `/api/v1`, need the `access_token` cookie (except the Meta webhook), and return errors as
`{"error": {"code": "snake_case", "message": "…"}}`. Validation errors are `422 validation_error` with
`error.details: [{loc, msg}]`. Tenant comes from the session only.

---

## Settings (P1-2)

### `GET /settings` → `SettingsOut`
```json
{
  "company_name": "Little Stars Kids Wear",
  "website": "https://littlestars.example",
  "description": "…", "ideal_customer_text": "…",
  "products": [{"name": "بيجامات قطن", "description": "قطن 100%", "price_range": "145-210 EGP", "min_order": "1 dozen"}],
  "target_regions": [{"governorate": "Cairo", "cities": ["Nasr City", "Heliopolis"]}, {"governorate": "Giza", "cities": []}],
  "language": "ar-EG", "tone": "friendly",
  "allowed_offers": "خصم لحد 10% على أول طلبية", "max_discount_percent": 10,
  "autonomy_mode": "approve_all", "first_touch_mode": "assisted", "agent_enabled": false,
  "daily_new_leads_target": 30, "daily_send_cap": 20,
  "quiet_hours_start": "10:00", "quiet_hours_end": "20:00",
  "working_days": [0, 1, 2, 3, 5, 6],
  "score_threshold": 6,
  "sequence_steps": [{"day_offset": 0, "purpose": "first_touch", "template": "intro"}, {"day_offset": 3, "purpose": "followup", "template": "followup"}],
  "demo_mode": true, "demo_whitelist": ["+201000009001"],
  "onboarding_completed": false,
  "telegram_connected": false,
  "warnings": ["demo_whitelist_empty"]
}
```
The row is created with defaults on first read. `warnings` (show as hints): `daily_send_cap_above_50`,
`demo_whitelist_empty` (demo mode blocks every send), `demo_mode_off` (real numbers are messaged).

### `PUT /settings` (partial) → `SettingsOut`
Send only the fields that changed; anything absent keeps its value. `null` is accepted only for `website`.
Unknown fields → 422. Owner only (member → `403 forbidden`).

| Field | Rule |
|---|---|
| `products` | 1–30 items; `name` 1–120 chars; `description`, `price_range`, `min_order` free text |
| `target_regions` | 1–27 items; `governorate` from `/settings/geo` (case-insensitive); `cities` from that governorate's list (English or Arabic name accepted, stored in English); governorates without a list accept free-text cities; `[]` = whole governorate |
| `language` / `tone` | `ar-EG`\|`en` / `friendly`\|`formal` |
| `max_discount_percent` | 0–50 |
| `autonomy_mode` | `approve_all`\|`approve_first_touch`\|`autopilot` |
| `first_touch_mode` | `assisted`\|`api_template` |
| `daily_new_leads_target` / `daily_send_cap` | 1–200 (warn in the UI above 50 for the cap) |
| `quiet_hours_start` < `quiet_hours_end` | `"HH:MM"`, checked against the stored value when only one is sent → `422 invalid_quiet_hours` |
| `working_days` | 1–7 values in 0–6 (Mon=0 … Sun=6), deduplicated and sorted |
| `score_threshold` | 1–10 |
| `sequence_steps` | 1–4 steps, `day_offset` 0–60 strictly increasing, first step `first_touch`, the others `followup`; `template` = the template purpose tag (`intro`/`followup`) |
| `demo_whitelist` | ≤ 5 Egyptian numbers in any spelling (`010…`, `+20…`, Arabic digits) → stored E.164 |
| `onboarding_completed: true` | needs `company_name`, ≥ 1 product and ≥ 1 region → else `422 onboarding_incomplete` (message lists what is missing). Unlocks `POST /icp/generate` and `POST /runs/sourcing`. |

### `GET /settings/geo`
```json
{"governorates": [{"name": "Cairo", "name_ar": "القاهرة", "cities": [{"name": "Nasr City", "name_ar": "مدينة نصر"}, …]}, …]}
```
27 governorates; city lists for Cairo, Giza, Alexandria, Qalyubia, Sharqia, Dakahlia, Gharbia.

---

## Run the agent (P2-2)

### `POST /runs/sourcing` `{"max_results"?: 1..200}` → `202 {"run_id": "…"}`
Default `max_results` = `daily_new_leads_target`. Poll `GET /runs/{run_id}` (P0-3). The finished run's
`output_summary`: `{created, duplicates, skipped, queries_run, queries_failed, api_requests, scoring_enqueued}`.
Errors: `400 onboarding_incomplete`, `400 no_active_icp`, `409 sourcing_already_running`, `503 queue_unavailable`.
A failed run's `error` contains `no_active_icp` or `all_searches_failed`.

---

## Channels (P3-2) — Settings → Channels

### `GET /channels`
```json
{
  "items": [{
    "channel": "whatsapp", "status": "connected",
    "phone_number_id": "1098765432101", "waba_id": "2000000000000",
    "display_phone_number": "+1 555 010 0000", "verified_name": "Little Stars", "quality_rating": "GREEN",
    "last_checked_at": "2026-11-20T09:00:00Z", "last_error": null,
    "templates": [{"id": "…", "name": "intro", "language": "ar", "category": "MARKETING", "status": "approved",
                   "purpose": "intro", "body_text": "أهلاً {{1}} …", "param_count": 2}]
  }],
  "webhook_url": "https://<tunnel>/api/v1/webhooks/whatsapp",
  "verify_token_configured": true,
  "app_secret_configured": true
}
```
`status`: `disconnected` (never connected) · `connected` · `error` (show `last_error`, e.g. `invalid_token: …`).

### `PUT /channels/whatsapp` `{"phone_number_id", "waba_id", "access_token"}` → the WhatsApp `ChannelOut`
Ids are digits (5–40), the token 20–1000 chars. The credentials are checked with Meta right away: a bad token
returns **200** with `status: "error"` and `last_error` (show it next to the form). On success the templates are
synced. The token is stored encrypted and never returned. Errors: `409 phone_number_in_use`,
`500 encryption_not_configured` (server `ENCRYPTION_KEY` missing), `403 forbidden` (members).

### `POST /channels/whatsapp/test` `{"to": "010 1234 5678"}`
→ `{"ok": true, "to": "+201012345678", "template_name": "hello_world", "provider_message_id": "wamid…", "error": null}`
Sends `hello_world` (or the first approved template). In demo mode `to` must be in the demo whitelist
(`400 not_whitelisted`). `400 invalid_phone`, `400 channel_not_connected`. A Meta error comes back as `ok: false`
with `error` (e.g. `recipient_not_allowed` = add the number in the Meta dashboard).

### `POST /channels/whatsapp/templates/sync` → `{"items": [TemplateOut], "total": n}`
`502 template_sync_failed`, `400 channel_not_connected`. Templates named `intro`/`followup` get that purpose.

### `PUT /channels/whatsapp/templates/{id}` `{"purpose": "intro" | "followup" | null}` → `TemplateOut`
The owner tags which template the agent uses for first touches / follow-ups (additive route, not in the
contract table yet).

### Message errors you may display (`messages.error`)
`opted_out`, `daily_cap_reached`, `demo_whitelist_empty`, `agent_paused`, `window_closed`, `no_mobile`,
`channel_not_connected`, `invalid_token`, `recipient_not_allowed`, `template_not_approved`,
`template_param_mismatch`, `rate_limited`, `undeliverable`, `outside_quiet_hours` (still queued; it goes out at the
next allowed time).

---

## Insights (P4-4) — InsightsCard, dashboard/reports variants

### `GET /insights`
```json
{
  "active": {
    "id": "…", "version": 2, "is_active": true, "created_at": "…",
    "insights": ["Kids clothing shops in Nasr City … — score them higher.", "…"],
    "icp_suggestions": ["Add Nasr City and Heliopolis as priority cities in Cairo."],
    "caveats": ["Only 10 outcomes so far …"],
    "stats": {
      "outcomes": 10, "won": 6, "lost": 4, "win_rate": 0.6, "won_value_egp": 174100.0,
      "contacted": 40, "replied": 29, "reply_rate": 0.725,
      "avg_hours_to_reply": {"won": 9.5, "lost": 21.0},
      "segments": {
        "category": [{"value": "Baby store", "n": 4, "won": 3, "lost": 1, "win_rate": 0.75,
                      "contacted": 12, "replied": 9, "reply_rate": 0.75}],
        "governorate": […], "score_band": […], "rating_band": […], "reviews_band": […], "website": […]
      }
    }
  },
  "history": [ /* every version, newest first, same shape */ ],
  "latest_run": {"id": "…", "status": "succeeded", "trigger": "manual", "created_at": "…", "finished_at": "…",
                 "error": null, "output_summary": {"version": 2, "insights": 4, "outcomes": 10}},
  "outcomes": 10,
  "min_outcomes": 3
}
```
`win_rate` / `reply_rate` are `null` when the denominator is 0. Bands: score `0-3|4-6|7-8|9-10|unscored`,
rating `<4.0|4.0-4.4|4.5+|no rating`, reviews `0-9|10-49|50-199|200+|no reviews`, website
`has website|no website`.

### `POST /insights/run` → `202 {"run_id"}` (Re-run button)
`400 not_enough_outcomes` (< 3), `409 feedback_already_running`, `503 queue_unavailable`. Poll `GET /runs/{id}`;
a run with too few outcomes finishes with `output_summary: {"skipped": "not_enough_outcomes"}`.

### `POST /insights/{id}/deactivate` → the version with `is_active: false` (Disable button)
After this the scorer uses no insights until the next run. `404` for another tenant's id.

---

## Webhook (Meta only) — `GET/POST /webhooks/whatsapp`
See `docs/setup-whatsapp.md`. No cookie; signed with `X-Hub-Signature-256`.
