# How adapters work in this repository

Business code depends on the Protocols and Pydantic models in `app/adapters/base.py`. It must obtain
concrete implementations only through `app/adapters/registry.py`; business code must not import a
concrete search, enrichment, channel or notification adapter directly.

## Mock versus real mode

Set `USE_MOCK_ADAPTERS=true` for deterministic local development and tests. The registry returns the
mock implementations and never makes external network calls.

Set `USE_MOCK_ADAPTERS=false` only with the real provider credentials. Real modules are imported lazily,
so unrelated unavailable providers do not break application startup.

## Adapter interfaces

- Search: `SearchSource.search(...)`
- Enrichment: `Enricher.enrich(...)`
- Channels: `ChannelAdapter.send_template(...)`, `send_text(...)`, `check_connection(...)`, and
  `list_templates(...)`
- Notifications: `Notifier.notify(...)`

## Adding a provider

1. Add a module next to the existing provider modules.
2. Implement the matching Protocol from `app/adapters/base.py`.
3. Register the module and class in `app/adapters/registry.py`.
4. Add provider-specific unit tests that use mock HTTP responses.
5. Document its environment variables without adding secret values.

Missing real adapters must raise a clear `NotImplementedError` naming the task that owns the provider.
