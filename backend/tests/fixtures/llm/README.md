# Mock LLM fixtures

With `USE_MOCK_LLM=true`, `llm_structured(run, name="<name>", ...)` returns the contents of `<name>.json` from this
folder (validated against the call's `output_model`). Without a fixture it returns a deterministic polyfactory
instance seeded by `name`. Add a realistic fixture for any agent whose output the UI or teammates rely on, e.g.
`icp_builder.profile.json` and `icp_builder.icp.json` (P1-3).
