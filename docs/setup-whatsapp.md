# WhatsApp Cloud API — developer setup (P0-1 first version; P3-2 completes the connection flow)

We use **only the official WhatsApp Cloud API** (Meta Graph API). Never use unofficial WhatsApp Web libraries:
they get numbers banned and break Meta's terms. Check Meta's current docs when anything below looks different —
the dashboard changes often.

> Safety: keep `demo_mode = true` (the default) in development. Every outbound message is then redirected to one
> of the tenant's whitelisted test phones (Settings → Demo phones, max 5). Never message real businesses.

## 1. Meta app + test number
1. Go to <https://developers.facebook.com/apps> → **Create app** → type **Business** → add the **WhatsApp** product.
2. WhatsApp → **API Setup** gives you a free **test phone number**, its **Phone number ID** and the
   **WhatsApp Business Account (WABA) ID**. Note both IDs.
3. **Recipient phones:** a test number can only message numbers you add under "To" (up to **5**). Add the team's
   phones and verify each with the code WhatsApp sends. Put the same numbers in the tenant's demo whitelist.
   Sending to any other number fails with `recipient_not_allowed` (Meta code 131030).
4. **Permanent token:** the token on API Setup expires in 24 h. For the demo create a **System User** in Business
   Settings → Users → System users, give it the app + the WABA with `whatsapp_business_messaging` and
   `whatsapp_business_management`, and generate a token that never expires. An expired token shows up as
   `invalid_token` (code 190); the channel goes to status `error` and the owner gets a notification.
5. App → Settings → Basic → **App secret** → `WHATSAPP_APP_SECRET` in `.env` (used to verify webhook signatures).
6. Pick any random string for `WHATSAPP_VERIFY_TOKEN` and the current Graph version for `WHATSAPP_GRAPH_VERSION`
   (e.g. `v27.0`).

## 2. Templates
The first message to a lead must be an **approved template**. Create them in WhatsApp Manager → Message templates
(category Marketing, language Arabic `ar`):

| name | body (example) | params |
|---|---|---|
| `intro` | أهلاً {{1}} 👋 معاك {{2}}. حابين نعرّفكم على تشكيلتنا الجديدة لملابس الأطفال. | 2 |
| `followup` | أهلاً تاني {{1}}، لسه مستنيين ردكم على التشكيلة الجديدة. | 1 |

Approval takes minutes to a day. Then in the app: **Settings → Channels → Sync templates**
(`POST /api/v1/channels/whatsapp/templates/sync`). Templates named `intro` / `followup` are tagged automatically;
any other template can be tagged with `PUT /api/v1/channels/whatsapp/templates/{id} {"purpose": "intro"}`.
Template parameters may not contain newlines, tabs or more than 4 spaces in a row — the adapter cleans them.

## 3. Webhook (receive replies and delivery statuses)
1. Run the API locally (`uv run poe api`) and expose it over HTTPS:
   `cloudflared tunnel --url http://localhost:8000` → copy the `https://….trycloudflare.com` URL into
   `PUBLIC_BASE_URL` and restart the API.
2. Meta app → WhatsApp → **Configuration** → Webhook → Edit:
   - Callback URL: `{PUBLIC_BASE_URL}/api/v1/webhooks/whatsapp` (also shown on the Channels page)
   - Verify token: your `WHATSAPP_VERIFY_TOKEN`
   Meta calls `GET …?hub.mode=subscribe&hub.verify_token=…&hub.challenge=…`; we answer with the challenge.
3. Under **Webhook fields**, **subscribe to `messages`** (this delivers both inbound messages and statuses).
4. **Subscribe the app to your WABA** (easy to miss with a system-user token): if Meta verifies the webhook but
   your replies never arrive, the app is not subscribed. Check `GET https://graph.facebook.com/v27.0/<WABA_ID>/subscribed_apps`
   (with the access token); if your app is missing, `POST` to the same URL once. Messages sent before that are not
   re-delivered — send them again. (Run the API with `USE_MOCK_ADAPTERS=false` for this test.)
5. Every POST is signed (`X-Hub-Signature-256`); a bad signature gets 401. Events are routed to the tenant by
   `metadata.phone_number_id` and stored idempotently (Meta retries are harmless).

The cloudflared URL changes on every restart: update `PUBLIC_BASE_URL` and the Callback URL each time.

## 4. Connect the number in the app
Settings → Channels (or `PUT /api/v1/channels/whatsapp`):
```json
{"phone_number_id": "1098765432101", "waba_id": "2000000000000", "access_token": "EAAG…"}
```
The token is stored encrypted (`ENCRYPTION_KEY`, Fernet). The response shows `status` (`connected` | `error`),
`display_phone_number`, `last_error` and the synced templates. Then send a test:
`POST /api/v1/channels/whatsapp/test {"to": "010 0000 0001"}` (in demo mode the number must be whitelisted).

## 5. The loop to check (P3-3 self-check)
1. Settings: `first_touch_mode = api_template`, demo whitelist = your phones, `agent_enabled = true`.
2. Approve 3 messages in /outreach → they arrive on the whitelisted phones (not the leads' numbers).
3. Reply from one phone → the message appears on that lead (demo route), the lead goes to `replied`, and
   `job_handle_inbound` is enqueued. Reply "stop" → the lead is `opted_out` and nothing more is sent.

## Error codes you will see (messages.error)
`window_closed` (131047, free text after 24 h) · `recipient_not_allowed` (131030, number not in the test list) ·
`template_not_approved` (132001) · `template_param_mismatch` (132000) · `invalid_token` (190) ·
`rate_limited` (4 / 80007 / 130429 / 131056; retried) · `undeliverable` (131026) · guardrails:
`opted_out`, `daily_cap_reached`, `demo_whitelist_empty`, `agent_paused`, `channel_not_connected`.

## Local testing without Meta
With `USE_MOCK_ADAPTERS=true` the channel is `app/adapters/channels/mock.py`: sends are recorded in memory, and
`simulate_inbound(...)` / `simulate_status(...)` build webhook bodies. Without `WHATSAPP_APP_SECRET` the webhook
accepts unsigned bodies in mock mode only.
