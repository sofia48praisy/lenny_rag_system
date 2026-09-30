# Lenny Growth Assistant — product requirements

## Discovery
The application serves product and growth practitioners using a separately ingested podcast transcript corpus. Public starter transcripts are downloaded with revision and checksum provenance.

## Persona and problem
A growth PM needs evidence-backed acquisition, activation, retention, and product-market-fit tactics without listening to hundreds of hours of audio. The PM asks a concrete question, inspects the underlying transcript, then develops an actionable essay or shareable HTML brief.

## Scope and acceptance
- Ingest Markdown/TXT episodes with guest, title, date, timestamp and provenance.
- Retrieve five passages from PostgreSQL/pgvector using local nomic embeddings; refuse below a configurable cosine similarity threshold.
- Stream answers through Ollama by default; support Anthropic through the same asynchronous interface and per-request selection.
- Persist sessions, messages, source snapshots and Markdown/HTML artifacts.
- Offer a responsive chat/artifact split view, visible source excerpts, session history, and downloads.
- Ship a Docker Compose stack, automated tests, and a reproducible demo procedure.

## Success metrics (targets, not measured claims)
Citation accuracy >=90% on a manually reviewed set of at least 20 in-domain answers; record supported claims / cited claims. Also track abstention on 10 out-of-domain questions. Warm local time to first token <4 seconds on stated hardware; report p50/p95, cold start separately. Artifact safety: no successful attacks in the documented sanitizer/isolation test suite. A finite test suite cannot prove absence of all XSS.

## Trade-offs
Default llama3.2:3b is accessible on CPU; 8B improves reasoning but consumes more RAM and time. Cloud routing improves generation but sends the question and retrieved excerpts to the configured provider and incurs usage charges. Embeddings remain local even with cloud generation. HNSW trades a small amount of recall for latency. Conservative retrieval thresholds may reject relevant questions and require calibration. A similarity threshold and valid citation labels do not guarantee semantic faithfulness; inspect evidence during evaluation.

## Boundaries
This is a single-user deployment. Authentication, tenant isolation, distributed rate limiting, backups and migrations beyond initial schema are production follow-ups. An external deployment requires an authenticated gateway. The application uses real transcript data and does not present simulated model output as generated evidence.
