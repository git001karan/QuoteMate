# QuoteMate — Development Guide

Local development, testing, and Docker instructions for the QuoteMate
WhatsApp Sales and Quotation Assistant (Cerevyn Solutions PS05).

## Prerequisites

- Python 3.11+ (CI and the Docker image use 3.11)
- `pip install -r requirements.txt`
- Optional: Docker, for containerized runs

## Run locally (no Docker)

```powershell
.\.venv\Scripts\Activate.ps1        # or: python -m venv .venv && pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health
- On startup the app creates `./quotemate.db` (SQLite) and seeds the product
  catalogue if the table is empty. No environment variables are required for
  local development; defaults come from `app/config.py`.

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

Tests create their own isolated SQLite databases under pytest's temporary
directory and never touch `./quotemate.db` production data or any secrets.

## Docker

Build the image (from the repository root):

```powershell
docker build -t quotemate:latest .
```

Run with a **mounted data directory** so the SQLite database survives
container restarts. On Windows, run from PowerShell:

```powershell
New-Item -ItemType Directory -Force .\data | Out-Null
docker run --rm -p 8000:8000 -v ${PWD}/data:/data quotemate:latest
```

On macOS/Linux:

```bash
mkdir -p data
docker run --rm -p 8000:8000 -v "$(pwd)/data:/data" quotemate:latest
```

- The container stores its database at `/data/quotemate.db`, backed by the
  mounted host folder, and seeds the catalogue on first start.
- Override settings with `-e`, e.g. `-e PORT=9000 -e DEFAULT_TAX_RATE=0.18`.
- The image runs as a non-root user and includes a Docker `HEALTHCHECK`
  against the app's real `/health` endpoint.
- Never place real credentials in the image, in `.env` files committed to Git,
  or in shell history. `.env` is gitignored; `.env.example` lists the
  variable names with safe defaults only.

## CI

`.github/workflows/ci.yml` runs on every push and pull request:

1. **test** — installs `requirements.txt` and runs the full pytest suite on
   Python 3.11 with an isolated `ENVIRONMENT=test` setting.
2. **docker-build** — build-only validation of the Dockerfile. The image is
   never pushed and no registry credentials are used.

## Production / Azure note

SQLite is fine for local development and demos. A production Azure deployment
should use a managed persistent database (e.g. Azure Database for PostgreSQL)
via the `DATABASE_URL` environment variable, or — if SQLite is retained — a
genuinely persistent, backed-up storage option. Details are intentionally left
to the Azure deployment milestone.
