# QuoteMate — Walkthrough (Milestone 9)

**Project:** QuoteMate — AI-Powered WhatsApp Sales and Quotation Assistant  
**Assessment:** Cerevyn Solutions PS05  
**Purpose:** Step-by-step guided tour of the backend, from first launch to confirmed quotation. Use this alongside `docs/demo-script.md` (timed 3–5 min presentation script) and `docs/tests.md` (scenario-to-test mapping).

---

## 0. Before you start

### Prerequisites

- Windows 10/11 with PowerShell 7 (or bash/zsh on macOS/Linux)
- Python 3.11 with the `.venv/` virtual environment already created
- (Optional) Docker for containerised run

### Activate the virtual environment

```powershell
.venv\Scripts\Activate.ps1
```

### Start the server

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open these in your browser:
- `http://127.0.0.1:8000/` — service root
- `http://127.0.0.1:8000/health` — health check
- `http://127.0.0.1:8000/docs` — interactive Swagger UI

---

## 1. Catalogue — what's available

The assistant knows 12 fictional electronics products, seeded from `app/data/products.json`:

| ID | Name | Price | Stock |
|----|------|-------|-------|
| KB-101 | Ergonomic Mechanical Keyboard | ₹3,499 | 25 |
| KB-102 | Compact Wireless Keyboard | ₹1,899 | 40 |
| MS-201 | Wireless Optical Mouse | ₹799 | 60 |
| MS-202 | Ergonomic Vertical Mouse | ₹1,599 | 30 |
| HP-301 | Noise-Cancelling Bluetooth Headphones | ₹4,999 | 20 |
| HP-302 | Lightweight Wired Gaming Headset | ₹2,199 | 35 |
| MN-401 | 27-Inch 4K UHD IPS Monitor | ₹22,499 | 15 |
| MN-402 | 24-Inch Full HD Office Monitor | ₹9,999 | 25 |
| WC-501 | 1080p Full HD Pro Webcam | ₹2,499 | 45 |
| HB-601 | 7-in-1 USB-C Multiport Hub | ₹1,999 | 50 |
| MC-701 | Studio USB Condenser Microphone | ₹3,899 | 18 |
| LP-801 | Adjustable Aluminum Laptop Stand | ₹1,299 | 75 |

Try: `GET http://127.0.0.1:8000/products`

---

## 2. Send your first message

Every customer message is a JSON POST to `POST /messages` (or `POST /webhook` for real WhatsApp):

```json
{
  "message_id": "MSG-001",
  "sender_id": "alice",
  "text": "I need 2 wireless mice and 1 gaming keyboard, send a quote",
  "timestamp": "2026-01-15T10:00:00Z"
}
```

### What happens under the hood

1. **Duplicate check** — `message_id` "MSG-001" is new, so processing continues.
2. **NLP classification** — `nlp_service` classifies intent as `quotation_request`, matches products `MS-201` (×2) and `KB-101` (×1), extracts quantities.
3. **Cart update** — items are added to Alice's per-sender cart.
4. **Draft quotation** — line totals, 18% tax, grand total computed with `Decimal` precision.
5. **Reply** — a structured `ProcessedMessageReply` is returned with `conversation_state: AWAITING_CONFIRMATION`.

---

## 3. Follow-up: provide a missing quantity

New customer, product named but no quantity:

```json
{
  "message_id": "MSG-002",
  "sender_id": "bob",
  "text": "I need wireless mice"
}
```

The assistant replies: *"How many units of Wireless Optical Mouse would you like to add?"* and sets `conversation_state: AWAITING_QUANTITY`. Bob then sends:

```json
{
  "message_id": "MSG-003",
  "sender_id": "bob",
  "text": "3"
}
```

The assistant remembers the pending product and completes the quotation.

---

## 4. Confirmation — creating an enquiry

Once Alice is happy with the draft:

```json
{
  "message_id": "MSG-004",
  "sender_id": "alice",
  "text": "yes, confirm"
}
```

The assistant:
- Re-validates stock
- Creates **exactly one** enquiry ID (`ENQ-<12 hex chars>`)
- Sets `quotation_status: CONFIRMED`
- Sets `conversation_state: CONFIRMED`

Sending the same confirmation again is idempotent — no duplicate enquiry.

---

## 5. Edge cases the walkthrough covers

| Scenario | What you see |
|----------|--------------|
| **Insufficient stock** | Requesting more than available is rejected before any enquiry is created |
| **Unknown product** | "Can you order a pizza?" → human handoff, not a quotation |
| **Duplicate message_id** | Replaying the same event returns `duplicated: true`, no state change |
| **Two independent users** | Alice and Bob have separate carts; neither sees the other's items |
| **Invalid input** | Empty `message_id` → HTTP 422 with a clear error |

---

## 6. Running the automated tests

```powershell
# All backend tests (90 tests)
.venv\Scripts\python.exe -m pytest tests/ -v

# With coverage report
.venv\Scripts\python.exe -m pytest tests/ --cov=app --cov-report=term

# Demo replay (events.json vs expected_outputs.json)
.venv\Scripts\python.exe scripts/demo.py
```

Expected result: all tests pass, demo reports `All checks passed.`

---

## 7. Docker

Build and run the container (Windows PowerShell):

```powershell
docker build -t quotemate:latest .
docker run --name quotemate -p 8000:8000 -v quotemate-data:/data quotemate:latest
```

The container runs as non-root `appuser`, exposes `/health`, and persists the SQLite database at `/data`.

---

## 8. GitHub Actions CI

`.github/workflows/ci.yml` runs on every push/PR:
1. **lint** — `ruff check`
2. **test** — `pytest` with coverage, coverage XML uploaded as artifact
3. **node** — frontend install + build
4. **docker-build** — `docker build` (no push, no credentials)

A `deploy-azure.yml` workflow is available for manual `workflow_dispatch` deployment with OIDC placeholders (no repo secrets committed).