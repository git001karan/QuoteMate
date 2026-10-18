# QuoteMate — WhatsApp Sales & Quotation Assistant

**Cerevyn Solutions · Chitkara University · PS05 software engineering assessment**

## Problem statement (PS05)
- understands product enquiries in natural language;
- collects quantities from the customer;
- calculates a quotation;
- asks for explicit confirmation before creating an enquiry;
- handles human handoff for unsupported requests.

QuoteMate is a local, AI-powered WhatsApp-style sales assistant. It understands natural-language product enquiries, collects quantities, keeps one cart per sender, calculates quotations from a fixed catalogue, asks for explicit confirmation before creating a quoted enquiry, and hands unexpected requests to a human reviewer.

## What it does now

- **Catalogue** — 12 fictional products (KB-101, MS-201, MN-401, etc.) seeded idempotently into SQLite from `app/data/products.json`.
- **Webhook / chat endpoint** — `POST /webhook` or `POST /messages` accept `message_id`, `sender_id`, `text`, and `timestamp`, then return a structured `ProcessedMessageReply`.
- **NLP classification** — trained sklearn/RapidFuzz intent classifier (`app/services/nlp_service.py`) splits requests into `quotation_request`, `product_inquiry`, `confirmation`, `clarification`, and out-of-domain.
- **Per-sender conversation state** — `ConversationModel` keyed by `sender_id`; states: `IDLE`, `AWAITING_QUANTITY`, `AWAITING_CONFIRMATION`, `CONFIRMED`, `DECLINED`.
- **Per-sender cart** — `CartItemModel` keyed by `sender_id` + `product_id`; each sender's cart is independent.
- **Quotation engine** — `QuotationService` calculates line totals, tax, and totals with `Decimal` precision and `DEFAULT_TAX_RATE` (18% by default).

## Technology stack

| Layer | Technology (real, in use) |
|---|---|
| Web framework | FastAPI (`app.main:app`) |
| ASGI server | Uvicorn (`uvicorn app.main:app --host 0.0.0.0 --port ${PORT}`) |
| DB ORM | SQLAlchemy 2.x with SQLite |
| Validation | Pydantic v2 |
| NLP / ML | scikit-learn, RapidFuzz |

## End-to-end message flow

1. A client or simulator sends an incoming event to `POST /webhook` or `POST /messages`.
2. `message_service` checks duplicate `message_id`, then persists the event.
3. `nlp_service` classifies intent and extracts candidate products and quantities from the text.
4. `message_service` updates the sender's conversation state and cart.
5. It calculates a draft quotation and replies to the customer with a text summary.
6. If the customer confirms, `quotation_service.confirm_for_sender()` re-validates stock and creates exactly one enquiry ID.
7. If the request is unsupported, `handoff_service` creates a human handoff record with full conversation context.

## Directory layout

```text
.
├── app/
│   ├── api/routes.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── data/products.json
│   └── services/
│       ├── catalogue_service.py
│       ├── conversation_service.py
│       ├── cart_service.py
│       ├── message_service.py
│       ├── nlp_service.py
│       ├── quotation_service.py
│       └── handoff_service.py
├── tests/
│   ├── conftest.py
│   ├── test_conversation_cart.py
│   ├── test_database.py
│   ├── test_handoff.py
│   ├── test_health.py
│   ├── test_nlp.py
│   ├── test_products.py
│   └── test_quotation.py
├── docs/
│   ├── assessment-checklist.md
│   ├── azure-plan.md
│   └── development.md
├── sample_data/
│   └── messages_dataset.json
├── Dockerfile
├── .dockerignore
├── requirements.txt
├── .env.example

## Prerequisites

- Windows 10/11 with PowerShell 7 (or any modern shell).
- Python 3.10+ (the repository includes a ready `.venv/` virtual environment).
- Docker and Docker Compose only if you want to run the container.

## Local startup — Windows PowerShell (recommended)

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Or combine:
```powershell
.\.venv\Scripts\Activate.ps1; uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open the following in your browser:
- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## General Python environments

```bash
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Environment configuration

All runtime behaviour is controlled by environment variables (`app/config.py` reads exactly these):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./quotemate.db` | SQLAlchemy database URL (local dev). |
| `APP_NAME` | `QuoteMate` | Application name shown in responses. |
| `ENVIRONMENT` | `development` | `development` or `production`. |
| `DEFAULT_TAX_RATE` | `0.18` | Tax rate as a decimal fraction; `0.18` = 18%. |
| `HOST` | `127.0.0.1` | Uvicorn host (local dev only). |
| `PORT` | `8000` | Uvicorn port. On Azure App Service, the platform supplies the port through `WEBSITES_PORT`. |

Example `.env` (never commit real secrets; `.env` is in `.gitignore`):


## Running the test suite

```bash
# With the virtual environment activated
.\.venv\Scripts\Activate.ps1
pytest tests/
```

Expected result:
```text
80 passed, 1 warning in ~25s
```

The suite covers:
- `tests/test_products.py` — catalogue size, endpoints, schema validation.
- `tests/test_health.py` — root, health, and `/docs` are reachable.
- `tests/test_conversation_cart.py` — separate carts, quantity entry, confirmation/decline, duplicates, persistence.
- `tests/test_quotation.py` — line totals, tax, rounding, stock issues, enquiry lifecycle.
- `tests/test_handoff.py` — handoff creation, context, duplicate protection, isolation, persistence.
- `tests/test_nlp.py` — intent classification, product matching, quantity extraction, and the wireless-mouse regression fix.

## API endpoints and verified request examples

All examples assume the server is running at `http://127.0.0.1:8000` with a local SQLite database initialized and products already seeded.

### Server health and documentation

```bash
GET  /health
GET  /
GET  /docs
GET  /openapi.json
```

### Catalogue

```bash
GET  /products        # 12 products, ordered by product id
GET  /products/KB-101 # Product details, HTTP 200
GET  /products/INVALID-999 # HTTP 404
```

### Incoming message (webhook-style)

```bash
curl -X POST http://127.0.0.1:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"message_id":"MSG-1","sender_id":"alice_001","text":"I need 2 wireless mice and 1 gaming keyboard, send a quote"}'
```

### Expected sanitized result for the multi-product request

```json
{
  "duplicated": false,
  "intent": "quotation_request",
  "conversation_state": "AWAITING_CONFIRMATION",
  "sender_id": "alice_001",
  "cart": {
    "items": [
      {"product_id": "KB-101", "quantity": 1, "line_total": 3499.0},
      {"product_id": "MS-201", "quantity": 2, "line_total": 1598.0}
    ],
    "subtotal": 5097.0
  },
  "quotation_id": "QT-<12 hex chars>",
  "quotation_status": "DRAFT",
  "enquiry_id": null,
  "needs_clarification": false,
  "is_unsupported": false
}
```

### Explicit confirmation

```bash
curl -X POST http://127.0.0.1:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"message_id":"MSG-2","sender_id":"alice_001","text":"yes, confirm"}'
```

### Expected sanitized result for the confirmation request

```json
{
  "conversation_state": "CONFIRMED",
  "enquiry_id": "ENQ-<12 hex chars>",
  "quotation_id": "QT-<12 hex chars>",
  "quotation_status": "CONFIRMED",
  "needs_clarification": false,
  "is_unsupported": false
}
```

### Missing quantity clarification

```bash
curl -X POST http://127.0.0.1:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"message_id":"MSG-3","sender_id":"alice_001","text":"I need wireless mice"}'
```

Expected assistant response:
```text
How many units of Wireless Optical Mouse would you like to add?
```

### Insufficient stock

```bash
curl -X POST http://127.0.0.1:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"message_id":"MSG-4","sender_id":"alice_001","text":"I need 30 Ergonomic Mechanical Keyboards"}'
```

Expected assistant response:
```text
I cannot prepare a quotation for the following items:
- Ergonomic Mechanical Keyboard (KB-101): insufficient stock (requested 30, available 25).
No enquiry ID has been created. Please adjust quantities or choose other products.
```

### Human handoff for unsupported request

```bash
curl -X POST http://127.0.0.1:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"message_id":"MSG-5","sender_id":"alice_001","text":"Can you order a pepperoni pizza for me?"}'
```

Expected assistant response:
```text
I'm sorry, I'm unable to help with that request. This has been passed to our human sales team for assistance. They will get back to you shortly.
Reference: your message has been logged for review.
```

## Docker and GitHub Actions

- Docker image: `docker build -t quotemate:latest .` then run with a persistent SQLite volume: `docker run --name quotemate -p 8000:8000 -v quotemate-data:/data quotemate:latest`.
- The image runs as a non-root `appuser`, exposes `/health`, and mounts a persistent SQLite database at `/data`.
- GitHub Actions CI workflow is at `.github/workflows/ci.yml` and runs `pytest tests/ -v --tb=short` on push and on pull requests (locally reproduced as `.venv\Scripts\python.exe -m pytest tests/ -q`).
- Hosted GitHub Actions has not been run in this environment; the workflow file is present and locally validated, but CI status on GitHub must be confirmed after the first push.
```ini
APP_NAME=QuoteMate
ENVIRONMENT=development
PORT=8000
HOST=127.0.0.1
DATABASE_URL=sqlite:///./quotemate.db
DEFAULT_TAX_RATE=0.18
```

`.env.example` in the repository contains only placeholder values.

## Database and catalogue seeding

- SQLite is used for local and container development. The connection is created when `app.main` starts via `app/database.py`.
- On startup the lifespan hook runs `init_db()`, then `catalogue_service.seed_catalogue_if_empty()`, which seeds products from `app/data/products.json` only when `ProductModel` rows are missing. Existing rows are never deleted or overwritten.
- The local file is `quotemate.db`. It is git-ignored; every pytest run uses an isolated `tmp_path` SQLite database.
- Dockerfile note: the image copies `app/data/products.json` and `sample_data/messages_dataset.json` at build time because both are read at import/startup. Container default `DATABASE_URL` points to `/data/quotemate.db`. Mount a persistent volume at `/data` to survive container restarts.
├── .gitignore
├── .github/workflows/ci.yml
└── README.md
```
| Tests | pytest + FastAPI TestClient |
| Container | Docker (`Dockerfile`) + GitHub Actions CI |
- **Explicit confirmation** — no enquiry ID is created until the sender confirms; repeated confirmation does not create duplicates.
- **Stock validation** — unknown, unavailable, and insufficient-stock issues are returned before any enquiry is created.
- **Human handoff** — unsupported requests create a persisted `HandoffModel` with conversation context.
- **Duplicate protection** — identical `message_id` is rejected with `duplicated: true`.
- **Persistence** — SQLite stores conversations, carts, quotations, handoffs, and message events.