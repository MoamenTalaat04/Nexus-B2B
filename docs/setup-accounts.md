# External accounts and API setup (P0-1)

This page documents account setup only. Never commit API keys, WhatsApp tokens or app secrets.

## LLM provider

The application uses the OpenAI-compatible Chat Completions adapter in
`backend/app/adapters/llm/openai_compatible.py`.

Create a provider account and set:

- `LLM_PROVIDER=openai_compatible`
- `LLM_BASE_URL` to the provider's OpenAI-compatible endpoint
- `LLM_API_KEY` to the provider key
- `LLM_MODEL_SMART` to the reasoning/writing model
- `LLM_MODEL_FAST` to the bulk/scoring model
- `LLM_MAX_CONCURRENCY` to a safe value for the provider's free tier
- `LLM_REASONING_MODELS` only for model IDs that accept `reasoning_effort`

Development should use fictional/demo data on free tiers because those requests may be used for model
training by some providers. Check the current provider documentation for JSON-schema support, tool-calling
support, model IDs, rate limits and data-retention terms before recording the final model names.

Example Gemini-compatible values are already documented in `.env.example`.

## Meta WhatsApp

Create or access the Meta business app, add WhatsApp, and record the test-phone IDs:

- Phone number ID
- WhatsApp Business Account ID
- Permanent System User token
- App secret
- Verify token
- Current Graph API version

Map them to:

- `WHATSAPP_APP_SECRET`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_GRAPH_VERSION`

The `phone_number_id`, `waba_id` and access token are entered through the channel API and the token is
stored encrypted in `channel_connections.secrets_encrypted`.

Create and submit the `intro` and `followup` Marketing templates in Arabic. Add no secret values to this
document. The operational webhook setup is in `docs/setup-whatsapp.md`.

## Google Places API (New)

Create a Google Cloud project, enable Places API (New), create an API key restricted to Places, and set a
daily quota plus a budget alert. Store the key only in:

- `GOOGLE_PLACES_API_KEY`

For development, prefer a Maps Demo Key or a billed key with a low daily quota/budget. Text Search can use
billable Enterprise fields; review Google's current pricing and field-mask costs before real searches.
