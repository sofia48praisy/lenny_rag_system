# Windows setup without Docker

This setup uses native Python/Node, portable PostgreSQL 16, pgvector and Ollama. The larger programs, database and models live under `D:\lenny-runtime` by default. Choose another location with `--destination` and `-RuntimeRoot` when needed. The application source remains in the project folder. Docker Compose is also supported.

## Memory considerations

16 GB RAM is recommended. The launcher uses llama3.2:3b, an 8,192-token context, and one loaded model at a time to reduce memory pressure. Smaller machines can run slowly. Switching between embeddings and generation may reload models. Finish or pause bulk ingestion before interactive generation on a memory-constrained machine.

## Reproduce on Windows

Use Python 3.11+ and Node 22+. Create `.venv`, install `backend/requirements.lock.txt`, and run `pnpm install --frozen-lockfile` in `frontend` (see README). Then, from the project folder:

```powershell
.venv\Scripts\python.exe scripts\download_runtime.py --destination D:\lenny-runtime
.\scripts\start-local.ps1
.venv\Scripts\python.exe scripts\pull_models.py
cd backend
..\.venv\Scripts\python.exe -m scripts.ingest ..\data\raw\lenny\podcasts
```

If you have not downloaded transcripts, first run `python backend/scripts/fetch_transcripts.py` from the project root. The runtime downloader gets official Ollama/EDB archives and the community-maintained MSVC pgvector build from `andreiramani/pgvector_pgsql_windows`. This is an unofficial Windows extension distribution, pinned to a release and verified against its published SHA-256. The container deployment and Linux CI use the pgvector project's own image. All downloaded hashes are recorded locally. Extraction checks that paths remain within the selected directory. It does not install Windows services or change machine-wide PATH.

The database initializer creates a new dedicated cluster bound to `127.0.0.1:5433`, uses a randomly generated SCRAM password and saves credentials only in ignored `.local` and `backend/.env` files. Existing `.env` files are preserved. The launcher starts background processes with hidden windows and writes logs under `.local`.

Open **http://127.0.0.1:5173**. Check **http://127.0.0.1:8000/api/health**. The application is ready only after both models and the vector index are available.

## Stop the database when finished

```powershell
& 'D:\lenny-runtime\postgres-community\pgsql\bin\pg_ctl.exe' -D 'D:\lenny-runtime\pgdata' stop -m fast
```

Stop the project-specific backend, Vite and Ollama processes through Task Manager or their owning terminal when no longer needed. Do not delete `pgdata` or model folders to stop a service. To move or remove this setup later, stop those processes first and back up wanted chat history.

## Sharing

Commit source, lockfiles, docs and tests only. `.gitignore` excludes credentials, local runtimes, dependency caches and raw transcripts. Other users download transcripts using the supplied script under the source dataset's terms.
