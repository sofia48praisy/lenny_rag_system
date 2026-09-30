# Lenny Growth Assistant

A retrieval-augmented assistant for exploring product and growth advice from Lenny's Podcast. Ask questions, inspect supporting transcript passages, and turn answers into Markdown essays or sandboxed HTML briefs.

## Features

- Local semantic search with nomic embeddings and PostgreSQL/pgvector.
- Streaming answers with episode and timestamp citations.
- Refusal when retrieved evidence falls below the relevance threshold.
- Ollama generation by default, with optional Anthropic routing.
- Persistent conversations, source snapshots, and writing artifacts.
- Markdown preview and isolated, sanitized HTML rendering.

## Stack

FastAPI · SQLAlchemy/asyncpg · PostgreSQL 16 + pgvector · Ollama · React · TypeScript · Vite · Tailwind CSS

## Run with Docker

```sh
git clone https://github.com/sofia48praisy/lenny_rag_system.git
cd lenny_rag_system
docker compose up --build
```

Open **http://localhost:3000** after initialization completes. The first launch downloads models and public transcripts, then builds the vector index. Models and database data persist across restarts.

```sh
docker compose logs -f model-init ingest
docker compose ps
```

Allow at least 15 GB free disk space; 16 GB RAM is recommended for local inference. CPU performance depends on the machine. Only the frontend is exposed, on localhost. The database and Ollama remain inside the Docker network.

**Windows without Docker:** follow [the native Windows setup](docs/windows-local.md). It supports placing the database and models on a separate drive.

## Configuration

Copy `.env.example` to `.env` when overriding Compose defaults. For native development, place configuration in `backend/.env` or export it in the shell.

| Setting | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_MODEL` | `llama3.2:3b` | Local generation model |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Local 768-dimensional embeddings |
| `DEFAULT_LLM_PROVIDER` | `ollama` | Default generation provider |
| `ANTHROPIC_API_KEY` | Unset | Enables optional cloud generation |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Configurable cloud model |
| `RETRIEVAL_THRESHOLD` | `0.55` | Minimum cosine similarity |
| `TOP_K` | `5` | Maximum retrieved passages |

Cloud mode sends the question and retrieved excerpts to Anthropic. Keys remain on the backend. Embeddings stay local regardless of the generation provider.

## Data and ingestion

The downloader uses the [official public Lenny starter corpus](https://github.com/LennysNewsletter/lennys-newsletterpodcastdata) and records its revision and file hashes in a local manifest. Raw transcripts are excluded from Git; use them according to the [dataset license](https://github.com/LennysNewsletter/lennys-newsletterpodcastdata/blob/main/LICENSE.md).

```sh
python backend/scripts/fetch_transcripts.py
cd backend
python -m scripts.ingest ../data/raw/lenny/podcasts
```

Ingestion extracts metadata and timestamps, recursively splits transcripts into overlapping passages, and stores vectors with an HNSW cosine index. Changed episodes are replaced atomically; unchanged content is skipped. To update the snapshot, run the downloader with `--refresh` and ingest again. Removed source files are not automatically purged from the database.

## Development and tests

Requirements: Python 3.11+, Node 22+, pnpm, and running PostgreSQL/pgvector and Ollama services. Create a Python virtual environment and install `backend/requirements.lock.txt`.

```sh
cd backend
python -m pytest -q
uvicorn app.main:app --reload
```

In another terminal:

```sh
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm test
pnpm dev
```

Open **http://localhost:5173**. Vite proxies `/api` to port 8000. API documentation is available at **http://localhost:8000/docs**. Set `TEST_DATABASE_URL` to a test PostgreSQL database to enable the real pgvector integration test. GitHub Actions runs backend, database integration, and frontend checks.

## Behavior and limitations

Retrieved passages are evidence, not instructions. The backend checks citation labels and declines when evidence is insufficient. A valid label does not prove every claim is supported; inspect the excerpts. Streaming tokens are provisional until final validation.

Conversation history persists, but retrieval currently uses the latest question alone. Follow-ups should include enough context. Essay mode targets approximately 1,250 words without forcing unsupported material. Calibrate the similarity threshold when changing the corpus or embedding model.

HTML artifacts use DOMPurify, a sandboxed iframe, and a restrictive CSP. Markdown does not render raw HTML. This is a single-user application; add authentication, tenant isolation, rate limiting, backups, and schema migrations before multi-user deployment.

## Documentation

- [Product requirements](docs/PRD.md)
- [Architecture and API contracts](docs/architecture.md)
- [Interface design](docs/design.md)
- [Native Windows setup](docs/windows-local.md)
