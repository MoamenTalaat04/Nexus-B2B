# Service modules

## Knowledge

`app.services.knowledge` provides tenant-scoped company knowledge retrieval:

- `get_knowledge_text(session, tenant_id, max_chars=120_000)` concatenates ready files in created-at
  order without cutting complete file blocks.
- `search_knowledge(session, tenant_id, query, k=5)` returns ranked keyword matches prefixed by filename.
- `extract_knowledge_text(...)` extracts and normalizes PDF, DOCX, Markdown and text files.

The API stores files under `UPLOAD_DIR/<tenant_id>/` and never exposes raw extraction exceptions or
filesystem paths. Upload/database failures are logged server-side and returned as safe contract error codes.
