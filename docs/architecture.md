# Architecture and data contracts

Browser (React/Vite/TypeScript/Tailwind) → Nginx `/api` proxy → FastAPI → PostgreSQL 16 + pgvector. Ollama supplies nomic-embed-text embeddings (768 dimensions) and local chat; Anthropic is an optional generation driver. LangChain's recursive text splitter is used as an abstraction primitive.

## Ingestion
Fetch the official public Lenny starter corpus into `data/raw`, recording repository revision, source URL and SHA-256 in a manifest. Parse YAML frontmatter and timestamped speech; split at recursive paragraph/sentence boundaries with a 2,800-character target and 400-character overlap (approximately 700/100 tokens; not exact token counts). Preserve the timestamp active at the chunk start. Embed in bounded batches. Replace each changed episode atomically; unchanged hashes and embedding model identifiers are skipped. A single ingestion advisory lock prevents concurrent rebuilds. Store source path and URL with each episode.

## Database
`episodes`: stable path ID, guest, title, publication date, URL, content hash, embedding model.
`chunks`: episode FK, ordinal, text, timestamp, vector(768); HNSW vector_cosine_ops index.
`sessions`: UUID, title, created_at, updated_at.
`messages`: UUID, session FK, role, text, JSONB source snapshots, created_at.
`artifacts`: UUID, assistant-message FK, type, content, title.
Database setup uses async SQLAlchemy and idempotent initial DDL; future schema changes require migrations.

## Retrieval and generation
Validate the query; embed `search_query: …`; order by cosine distance, take K=5 and discard candidates below threshold. Only the configured embedding model's corpus is eligible. No eligible evidence means a fixed refusal and no LLM call. Prompts delimit untrusted transcript text and require exact `[Episode: Guest, Timestamp/Topic]` source labels. Generated labels are checked against retrieved evidence; invalid or missing citations fail closed at completion. This is a structural guard, not an entailment verifier. Streaming tokens are provisional; the final message event is authoritative. Conversation history is persisted and displayed, but retrieval uses the current question alone; follow-ups should be self-contained.

## HTTP contracts
- `POST /api/sessions` `{title?}` → session.
- `GET /api/sessions` → recent sessions.
- `GET /api/sessions/{uuid}` → session and messages with artifacts/sources.
- `POST /api/chat` `{session_id, question, provider?, mode: answer|essay|html}`. Optional `X-LLM-Provider` overrides body/default. Response is SSE over fetch: `sources`, `token`, `message`, `done`; failures use `error`. Events contain JSON. Partial failed responses are not stored as completed assistant messages. HTTP validation occurs before stream start.
- `GET /api/health` → DB, chunk count/index presence, embedding model availability, Ollama chat availability, configured providers; returns 503 if local readiness is incomplete.

## Reliability and safety
Bounded connect/read timeouts; retry safe embedding calls on transient failures; do not replay partially delivered generation. Structured JSON request logs exclude questions, excerpts and secrets. Same-origin production API with explicit development CORS. HTML is sanitized, placed in an opaque-origin sandbox iframe and guarded by a restrictive CSP denying external resources, forms and navigation. Markdown disallows raw HTML. Per-session PostgreSQL advisory locking rejects concurrent generations. Failed generation rolls back its messages; frontend retains the draft for retry.
