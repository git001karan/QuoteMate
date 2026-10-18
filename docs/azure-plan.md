# QuoteMate — Azure Deployment Plan (Milestone 10)

**Project:** QuoteMate — AI-Powered WhatsApp Sales and Quotation Assistant
**Assessment:** Cerevyn Solutions PS05
**Status of this document:** Deployment **plan only**. No Azure resources have
been created, no images pushed, and nothing has been deployed. Every command
below is untested against a live subscription. All names in `<angle brackets>`
are placeholders — no real subscription IDs, resource IDs, domains, or
credentials appear anywhere in this file.

---

## A. Architecture

```
                         GitHub (repo + Actions)
                          |  push / pull request
                          v
                 +-------------------+        docker build (validation only,
                 |  GitHub Actions   |        no push, no credentials)
                 |  CI: tests + build|
                 +-------------------+

  Webhook          Azure (resource group <RESOURCE_GROUP>, region <REGION>)
  simulator /          +----------------------------------------------+
  customer  --HTTPS--> | Azure App Service (Linux, "Web App for          |
  client               | Containers")  <APP_NAME>.azurewebsites.net     |
                       |                                              |
                       |  Container: <ACR_NAME>.azurecr.io/            |
                       |             quotemate:<IMAGE_TAG>             |
                       |  - listens 0.0.0.0:${PORT} (uvicorn)          |
                       |  - Health check path: /health                 |
                       |  - App settings: DATABASE_URL,                |
                       |    DEFAULT_TAX_RATE, ENVIRONMENT, APP_NAME,   |
                       |    WEBSITES_PORT, PORT                        |
                       |        |                      |               |
                       |        v                      v               |
                       |  [Option 1 - RECOMMENDED]  [Option 2/3]       |
                       |  Azure Database for        SQLite file on     |
                       |  PostgreSQL (managed)      mounted volume     |
                       |  via DATABASE_URL          (demo-grade only)  |
                       +----------------------------------------------+
```

Components:

| Component | Role |
|---|---|
| Webhook simulator / test client | Sends `POST /messages` events (message ID, sender ID, timestamp, text) — same as the local simulator used in testing |
| Azure App Service for Containers | Hosts the Docker image built from this repo's `Dockerfile` |
| Azure Container Registry (ACR) or another supported registry | Stores the pushed image; App Service pulls it |
| App Service configuration | Injects environment variables into the container at runtime (no secrets in the image) |
| Persistent database | Managed PostgreSQL (recommended) or a carefully reviewed persistent-storage option — see section D |
| GitHub Actions CI (`.github/workflows/ci.yml`) | Runs the 80-test suite and a build-only image validation on every push/PR |
| Health monitoring | App Service Health Check probes `/health`; the image also carries a Docker `HEALTHCHECK` against the same endpoint |

Request flow: client → HTTPS → App Service router → container port
(`WEBSITES_PORT`) → uvicorn → FastAPI `/messages` → services → SQLite or
managed database → structured JSON reply.

---

## B. Deployment prerequisites

1. **Azure subscription** with permission to create resource groups, App
   Service plans/apps, and container registries (e.g. Contributor on the
   resource group). *Creating these resources may incur charges — see H.*
2. **Azure CLI** installed and logged in (`az --version`, `az login`).
3. **A container registry**: Azure Container Registry (recommended) or any
   registry App Service can pull from (Docker Hub, etc.).
4. **Docker** installed and running (verified working on this machine — the
   Milestone 9 image build completed with exit code 0).
5. **GitHub repository** with Actions enabled (the workflow exists but has
   **not yet run** — see G).

Configuration placeholders used below — replace all of them:

| Placeholder | Meaning |
|---|---|
| `<SUBSCRIPTION_ID>` | Your Azure subscription GUID |
| `<RESOURCE_GROUP>` | Resource group name, e.g. `rg-quotemate` |
| `<REGION>` | Azure region, e.g. `westeurope` |
| `<ACR_NAME>` | Globally unique ACR name (becomes `<ACR_NAME>.azurecr.io`) |
| `<PLAN_NAME>` | App Service plan name |
| `<APP_NAME>` | Web app name (becomes `<APP_NAME>.azurewebsites.net`) |
| `<IMAGE_TAG>` | Image tag, recommended: the Git commit SHA |
| `<PREV_IMAGE_TAG>` | Previous good tag, for rollback |
| `<ACR_USERNAME>` / `<ACR_PASSWORD>` | Registry credentials *if* using admin auth (prefer managed identity, section F) |

Image publication (local, after `az acr login`):

```bash
docker build -t <ACR_NAME>.azurecr.io/quotemate:<IMAGE_TAG> .
docker push <ACR_NAME>.azurecr.io/quotemate:<IMAGE_TAG>
```

## C. Container configuration

### What the existing Dockerfile does (verified — Milestone 9)

- Base: `python:3.11-slim` (matches the interpreter the 80 tests pass on).
- `pip install -r requirements.txt`.
- Copies `app/` **and** `sample_data/` — both are required at **import time**:
  `nlp_service` trains the intent classifier from
  `sample_data/messages_dataset.json` when the module loads, and
  `catalogue_service` validates `app/data/products.json` on construction.
  Omitting either file would crash startup.
- Runs as non-root `appuser` (uid 1000); creates writable `/data`.
- `ENV DATABASE_URL="sqlite:////data/quotemate.db"`, `ENVIRONMENT=production`,
  `PORT=8000` — container defaults only; the application's own default in
  `app/config.py` (`./quotemate.db`) is untouched.
- `VOLUME ["/data"]`, `EXPOSE 8000`.
- `HEALTHCHECK` polls `http://127.0.0.1:${PORT}/health` with Python stdlib.
- Startup command:

  ```dockerfile
  CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
  ```

  The ASGI entrypoint is **`app.main:app`** (confirmed in `app/main.py`).

### Port handling on Azure App Service (verified against Microsoft docs)

Two settings matter and do different jobs for **custom** containers:

| Setting | Who reads it | Purpose |
|---|---|---|
| `WEBSITES_PORT` | App Service platform | Tells the platform which container port to route traffic to. Microsoft's guidance for Web App for Containers: it "should ideally always be used", and **if both are set, `WEBSITES_PORT` takes precedence**. |
| `PORT` | **This image** (Dockerfile CMD + HEALTHCHECK) | uvicorn binds `--port ${PORT}`. Azure's docs note a custom-container app may "need to add both `WEBSITES_PORT` and `PORT`" when the codebase references `PORT`. |

**Required App Service configuration:** set **both** `WEBSITES_PORT=8000` and
`PORT=8000` as application settings, so the platform routes to container port
8000 and the container's own CMD binds it explicitly.

### Health endpoint (verified locally)

`GET /health` → HTTP 200:

```json
{"status": "healthy", "timestamp": "<UTC ISO-8601>", "service": "QuoteMate", "version": "0.1.0"}
```

- Configure App Service **Health Check** path to `/health` (portal: App →
  Health check); the platform then probes this path and removes unhealthy
  instances from rotation.
- Warm-up: App Service pings `/robots933456.txt` before routing organic
  traffic. FastAPI returns 404 for it — per Microsoft's docs, *any* response
  (including 404) counts as "ready" unless `WEBSITE_WARMUP_STATUSES` is
  configured, so no change is needed.
- The in-image Docker `HEALTHCHECK` also reported `healthy` in local testing;
  on App Service the platform-level Health Check governs routing.

### Changes required before a real deployment

1. **No application code changes** are needed for a basic container deploy.
2. Image must exist in a registry App Service can pull from (section B).
3. Set `WEBSITES_PORT` / `PORT` app settings (above).
4. Set Health Check path `/health`.
5. For a managed database (recommended), the adaptations in section D are
   required — they are **not** implemented yet.

## D. Database persistence

### Why a container-local SQLite file is not durable on App Service

The container stores its database at `/data/quotemate.db`. On App Service:

- Container instances are **replaced** by the platform during configuration
  changes, image updates, platform maintenance, and scale events. Anything
  written inside the container's own filesystem is **lost** when the instance
  is replaced.
- On **scale-out** (multiple instances), each instance would run its own
  private SQLite file: writes diverge, reads are stale, and quotation/cart
  state becomes inconsistent. There is no shared file across instances.
- There is no snapshot/backup story for a file inside a replaced container.

The Milestone 9 volume-mount verification (`-v …/data:/data`, data survived
`docker restart`) proves persistence for **local Docker only** — it says
nothing about App Service durability.

### Options compared

| Option | What it needs | Tradeoffs | Verification status |
|---|---|---|---|
| **1. Managed database — Azure Database for PostgreSQL flexible server** (or Azure SQL) | Point `DATABASE_URL` at e.g. `postgresql+psycopg://<USER>:<PASSWORD>@<PG_HOST>:5432/quotemate`; **add a driver package (e.g. `psycopg`) to `requirements.txt`** and test | + Durable, backed up, scales out safely, no per-instance file. − Ongoing cost, network/firewall setup, DB password must live as a secret (Key Vault reference), **application adaptation required** | **Not verified.** The code reads `DATABASE_URL` verbatim (`app/config.py`) and passes it to `create_engine` (`app/database.py`); SQLite-specific behaviour (`check_same_thread`, `PRAGMA foreign_keys`) is guarded by `DATABASE_URL.startswith("sqlite")`, so other SQLAlchemy URLs would flow through untouched. **However: no DB driver is in `requirements.txt`, the `init_db()` column migrations have never run against a real server, and no managed-database test has ever executed.** Compatibility must not be assumed. |
| **2. Retain SQLite + mounted persistent storage (Azure Files)** | Mount an Azure Files share and point `DATABASE_URL` at it | − **Microsoft's storage-mount documentation explicitly states: "Don't use storage mounts for local databases, such as SQLite, or for any other applications and components that rely on file handles and locks."** SQLite locking over an SMB share is unreliable, and it still does not fix multi-instance divergence. | **Not configured, not recommended, not verified.** |
| **3. Demo-grade: single instance, accept data loss risk** | Nothing — container-local `/data` on one instance | + Zero extra cost/config. − Data can vanish on platform replacement; no backups; must **never scale out** in this mode | Honest description only; acceptable for a short-lived assessment demo, **not** for production. |

### Recommendation

- **Production:** Option 1 (managed PostgreSQL) after completing and testing
  the adaptation — the only option that is durable, backup-able, and safe
  under scale-out. Its cost and setup effort are the price of those
  properties.
- **Assessment demo:** Option 3, or keep demonstrating on local Docker where
  the mounted-volume behavior is already verified. Stay at a single instance.
- **Local development is unchanged:** `app/config.py` keeps its SQLite
  default (`./quotemate.db`); nothing in this plan modifies the existing
  local SQLite workflow.

---

## E. Environment variables and security

### Variables the application actually reads (verified by code search)

Defined in `app/config.py` — these are the **only** variables the Python code
reads via `os.getenv`:

| Variable | Code default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///<repo>/quotemate.db` | SQLAlchemy engine URL (any SQLAlchemy URL type) |
| `APP_NAME` | `QuoteMate` | Application name metadata |
| `ENVIRONMENT` | `development` (image sets `production`; CI sets `test`) | Deployment environment label |
| `DEFAULT_TAX_RATE` | `0.18` | Quotation tax rate (Decimal, read as float then converted) |

Variables consumed by the **container** (not the Python code):

| Variable | Where read | Purpose |
|---|---|---|
| `PORT` | Dockerfile CMD + HEALTHCHECK | uvicorn bind port (image default 8000) |
| `WEBSITES_PORT` | App Service platform | Platform → container routing port (Azure-only; **not in `.env.example` because it has no meaning outside App Service**) |

Note: `.env.example` also lists `HOST=127.0.0.1`, but **no code reads
`HOST`** — the bind address comes from the Dockerfile CMD
(`--host 0.0.0.0`) or the uvicorn CLI flag. It is documentation for local
manual runs only.

### Secure configuration

- Set production values as **App Service application settings**
  (Configuration → Application settings). They are injected as environment
  variables at runtime and are **never baked into the image** — the image
  contains no secrets (`.dockerignore` excludes `.env*`, `.git`, `*.db`).
- If a secret is ever needed (e.g. a database password inside
  `DATABASE_URL`), store it in **Azure Key Vault** and reference it with a
  Key Vault app-setting reference (`@Microsoft.KeyVault(SecretUri=…)`) —
  App Service surfaces these via `WEBSITE_KEYVAULT_REFERENCES`. Do not put
  passwords in command lines or commit them to Git.
- Repository hygiene (already in place): `.env` is gitignored and
  `git check-ignore` confirms no `.env`/`.db` file is tracked; only the
  placeholder file `.env.example` is committed.

### Broader security posture

- **HTTPS:** App Service serves TLS on `*.azurewebsites.net` by default;
  enforce HTTPS-only and disable old TLS versions in the platform settings.
- **Least privilege:** grant the deployer only what is needed (e.g.
  Contributor on one resource group); pull images with a **managed
  identity** rather than registry admin passwords (Microsoft recommends
  managed identity for container pulls).
- **Backups:** automated backups are a property of the *managed database*,
  not the container — one more reason Option 1 is the production answer.
  Export/download quotation data periodically if running demo-grade.
- **Log hygiene:** the app logs to stdout (`PYTHONUNBUFFERED=1`); never
  print `DATABASE_URL`, registry passwords, or connection strings to logs.
  Keep application logs at `information` level in App Service.

## F. Deployment steps

> **Nothing below has been executed.** Every command is a plan template.
> Lines marked **\[CREATES RESOURCES — MAY INCUR CHARGES\]** create billable
> Azure resources. Replace every `<PLACEHOLDER>`. Never paste real
> credentials into Git, shell history, or this document.

### F.1 Authenticate and pick the subscription

```bash
az login
az account set --subscription <SUBSCRIPTION_ID>
az account show --query "{sub:name, tenant:tenantId}" -o table   # sanity check
```

### F.2 Resource group and registry

```bash
# [CREATES RESOURCES — MAY INCUR CHARGES]
az group create --name <RESOURCE_GROUP> --location <REGION>

# [CREATES RESOURCES — MAY INCUR CHARGES] Basic SKU is billable
az acr create --resource-group <RESOURCE_GROUP> --name <ACR_NAME> --sku Basic

az acr login --name <ACR_NAME>
```

### F.3 Build and publish the image (from the repo root)

```bash
# Tag with the commit SHA for traceable rollbacks
export IMAGE_TAG=$(git rev-parse --short HEAD)

docker build -t <ACR_NAME>.azurecr.io/quotemate:<IMAGE_TAG> .
docker push <ACR_NAME>.azurecr.io/quotemate:<IMAGE_TAG>
```

Consistent with the actual `Dockerfile` (no custom `CMD` overrides needed —
the image's CMD already reads `${PORT}`).

### F.4 App Service plan and web app

```bash
# [CREATES RESOURCES — MAY INCUR CHARGES] Linux plan; Basic (B1) is the
# lowest tier that supports custom containers — verify current SKU support
# in the Azure docs before choosing.
az appservice plan create --name <PLAN_NAME> --resource-group <RESOURCE_GROUP> \
  --sku B1 --is-linux

# [CREATES RESOURCES — MAY INCUR CHARGES]
az webapp create --resource-group <RESOURCE_GROUP> --plan <PLAN_NAME> \
  --name <APP_NAME> \
  --deployment-container-image-name <ACR_NAME>.azurecr.io/quotemate:<IMAGE_TAG>
```

### F.5 Registry authentication (prefer managed identity)

Microsoft recommends managed identity for pulling from ACR:

```bash
# Enable system-assigned identity on the web app
az webapp identity assign --name <APP_NAME> --resource-group <RESOURCE_GROUP>

# Grant the identity ACR pull access
az role assignment create --assignee <PRINCIPAL_ID> --scope <ACR_RESOURCE_ID> \
  --role "AcrPull"
```

`<PRINCIPAL_ID>` comes from the `identity assign` output (principalId) and
`<ACR_RESOURCE_ID>` from `az acr show --name <ACR_NAME> --query id -o tsv`.
Note (per Microsoft docs): ACR must allow ARM audience tokens for
managed-identity pulls, otherwise image pulls fail with an `UNAUTHORIZED`
/token-validation error.

Alternative (quick start, less desirable — admin credentials):

```bash
az webapp config container set --name <APP_NAME> --resource-group <RESOURCE_GROUP> \
  --container-image-name <ACR_NAME>.azurecr.io/quotemate:<IMAGE_TAG> \
  --docker-registry-server-url https://<ACR_NAME>.azurecr.io \
  --docker-registry-server-user <ACR_USERNAME> \
  --docker-registry-server-password <ACR_PASSWORD>
```

### F.6 Application settings

```bash
# [CHANGES CONFIGURATION of existing resources]
az webapp config appsettings set --name <APP_NAME> --resource-group <RESOURCE_GROUP> \
  --settings \
    WEBSITES_PORT=8000 \
    PORT=8000 \
    ENVIRONMENT=production \
    DEFAULT_TAX_RATE=0.18 \
    APP_NAME=QuoteMate \
    DATABASE_URL="sqlite:////data/quotemate.db"
```

- `WEBSITES_PORT=8000` / `PORT=8000` per section C.
- `DATABASE_URL` shown with the **demo-grade** container-local path per
  section D Option 3. For Option 1, substitute the managed-server URL and
  keep its password in Key Vault as a reference — never in shell history.
- Also enable **Health check** path `/health` (portal: App → Health check).

### F.7 Verify the deployment (smoke tests)

```bash
# Resolve the hostname (no invented domains)
az webapp show --name <APP_NAME> --resource-group <RESOURCE_GROUP> \
  --query defaultHostName -o tsv
# -> <APP_NAME>.azurewebsites.net

curl -sS https://<APP_NAME>.azurewebsites.net/health
# expect: {"status":"healthy",...}

curl -sS https://<APP_NAME>.azurewebsites.net/
# expect: {"service":"QuoteMate",...,"status":"online",...}

curl -sS https://<APP_NAME>.azurewebsites.net/products | python -c \
  "import sys,json; print(len(json.load(sys.stdin)))"
# expect: 12  (catalogue seeded on first start)

# End-to-end event (unique IDs each run):
curl -sS -X POST https://<APP_NAME>.azurewebsites.net/messages \
  -H "Content-Type: application/json" \
  -d '{"message_id":"smoke-001","sender_id":"smoke-tester","timestamp":"2026-10-18T10:00:00Z","text":"I need 2 wireless mice, please send a quote"}'
# expect: reply_text + cart containing MS-201 only
```

### F.8 Logs

```bash
# Stream container/application logs (enable "Container / Docker logs"
# in the portal first, or:)
az webapp log config --name <APP_NAME> --resource-group <RESOURCE_GROUP> \
  --docker-container-logging filesystem

az webapp log tail --name <APP_NAME> --resource-group <RESOURCE_GROUP>
```

Look for uvicorn startup lines, the lifespan `init_db()`/seeding pass, and
tracebacks. No secrets should appear (log-hygiene rule, section E).

### F.9 Rollback

Keep previous image tags in ACR; rollback is a config change, not a rebuild:

```bash
# [CHANGES CONFIGURATION] repoint to the previous known-good tag
az webapp config container set --name <APP_NAME> --resource-group <RESOURCE_GROUP> \
  --container-image-name <ACR_NAME>.azurecr.io/quotemate:<PREV_IMAGE_TAG>
```

App Service restarts the container automatically after the change; re-run
F.7 smoke tests. If using managed identity pulls, the same command with the
older tag is sufficient — the identity permissions are unchanged.

## G. CI/CD and verification

### What is verified locally vs. what needs GitHub or Azure

| Check | Status |
|---|---|
| Full test suite (80 passed, 1 third-party warning) | ✅ **Verified locally** (`.venv`, Python 3.11.5) |
| Docker image build (exit 0, 686MB) | ✅ **Verified locally** (Docker Desktop, M9) |
| Container start, `/health`, 12 products, non-root, volume persistence across restart, `HEALTHCHECK=healthy` | ✅ **Verified locally** (M9) |
| `ci.yml` syntax (YAML parse, both jobs + triggers present) | ✅ **Verified locally** |
| GitHub Actions run on a real push | ⛳ **Not yet run** — requires pushing this repository to GitHub |
| `docker push` to a registry | ⛳ **Not executed** |
| Any `az …` command / Azure resource | ⛳ **Not executed** — plan only |
| Azure smoke tests (F.7) | ⛳ **Pending a real deployment** |

### Verifying the first GitHub Actions run (after pushing)

1. Push the repository (and branches/PRs) to GitHub:
   `git push origin master` — then open the repo → **Actions** tab.
2. Expect workflow **CI** with each push/PR, containing two jobs:
   - **`Full automated test suite (Python 3.11)`** — must show
     `80 passed, 1 warning`; the single warning is the known
     starlette/httpx deprecation, not a failure.
   - **`Docker image build validation (no push)`** — must end at
     `naming to docker.io/library/quotemate:ci done`; **no push occurs and
     no registry credentials exist in the workflow**.
3. If a job fails: open its log; pytest failures print `--tb=short`
   tracebacks and the exact failing test id — reproduce locally with
   `.\.venv\Scripts\python.exe -m pytest <test-id> -v`. Docker job failures
   reproduce with `docker build -t quotemate:ci .`.
4. A green run is the first proof the workflow itself works — until then,
   treat CI as *configured but unproven* (it mirrors commands that pass
   locally, but hosted runners differ).

### Post-deployment troubleshooting

| Symptom | Likely cause | Check |
|---|---|---|
| App never becomes ready / 502 | Wrong port | `WEBSITES_PORT` set to 8000? Container logs show uvicorn bound to 8000? |
| `UNAUTHORIZED` / token validation failed on pull | ACR ↔ managed identity | ARM audience tokens enabled on ACR? `AcrPull` granted to the app's principal? |
| `/health` returns 500/timeout | Startup crash (missing `sample_data/` or `app/data/`, or migration error) | `az webapp log tail`; look for import-time `FileNotFoundError` or SQL errors |
| `/products` returns 0 items | Seeding didn't run or DB wiped | Confirm lifespan ran (`init_db` + seed); re-check `DATABASE_URL` path/writability |
| Data disappeared after redeploy | Expected under Option 3 (container-local SQLite) | Section D — this is the documented durability gap, not a bug |
| Tests pass locally, CI fails | Python version or dependency drift | Compare workflow Python (3.11) with local; check `pip install` log |

---

## H. Cost and limitations

### Cost (no exact prices are claimed here)

**All Azure resources referenced in section F may incur charges.** In
particular: the **App Service plan** (billed per instance-hours; custom
containers need a paid tier — Basic or above — verify current SKU support),
**Azure Container Registry** (Basic SKU billing), **Azure Database for
PostgreSQL/SQL** if Option 1 is chosen (compute + storage + backups), and
**outbound bandwidth**. Exact prices vary by region, SKU, and usage —
consult the **Azure Pricing Calculator** and, for the assessment, the Azure
free account / free-tier credits if eligible. **Delete the resource group
when the demo is over** to stop charges:
`az group delete --name <RESOURCE_GROUP> --yes --no-wait`.

### Outstanding work before a real production deployment

1. **Run the GitHub Actions workflow** on an actual GitHub push (G).
2. **Decide the database path** (section D): implement + test the managed
   PostgreSQL adaptation (driver in `requirements.txt`, migrations verified
   against a real server) or accept documented demo-grade limitations.
3. **Publish an image** to a registry and complete F.1–F.9 once — this plan
   has never been executed end-to-end.
4. **Secrets**: move any future credential into Key Vault references.
5. **Monitoring/alerting** (App Insights, health-check alerts), automated
   **backups + a restore drill** for the chosen database.
6. **README and recorded demonstration** (Milestone 11) are still missing.
7. Optional hardening: image vulnerability scanning, image digest pinning,
   staging slots (needs Standard tier), autoscale policy.

### Honest limitations of this document

- This is a **deployment design**, not a deployment. No resource exists, no
  image is published, and no command in section F has been run.
- PostgreSQL/Azure SQL compatibility of `init_db()` migrations and the app
  under a non-SQLite engine is **unverified** (section D).
- Azure CLI flags follow current Microsoft documentation but were not
  executed here; confirm flags against `az … -h` before use.
- Nothing in this milestone changed application business logic, tests, or
  the local SQLite workflow.






