# QuoteMate — Demo Script (Milestone 11)

**Project:** QuoteMate — AI-Powered WhatsApp Sales and Quotation Assistant
**Assessment:** Cerevyn Solutions PS05
**Purpose:** Walk through the core customer-facing flows in order, showing what to type (simulate via `POST /messages`) and what the assistant should reply.

## Prerequisites

- The server is running locally: `uvicorn app.main:app --host 127.0.0.1 --port 8000`
- The virtual environment is activated: `.\.venv\Scripts\Activate.ps1`
- Products are seeded (happens automatically on startup).

Send every request as:

```bash
curl -X POST http://127.0.0.1:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"message_id":"<UNIQUE_ID>","sender_id":"<CUSTOMER_ID>","text":"<MESSAGE>"}'
```

Use a fresh `sender_id` per demo scenario unless the scenario explicitly continues a previous conversation. Reusing the same `sender_id` continues that customer's cart and conversation state.

## Scenario 1 — Multi-product quotation request

**Goal:** Show the assistant understanding natural language, adding multiple products to one cart, calculating a draft quotation, and awaiting confirmation.

### Step 1 — Send the enquiry

```json
{
  "message_id": "demo-1-1",
  "sender_id": "demo-customer-a",
  "text": "I need 2 wireless mice and 1 gaming keyboard, send a quote"
}
```
## Scenario 2 — Explicit confirmation creates exactly one enquiry

**Goal:** Show that an enquiry ID is only created after the customer explicitly confirms, and that repeating confirmation does not duplicate it.

### Step 2 — Confirm

```json
{
  "message_id": "demo-2-1",
  "sender_id": "demo-customer-a",
  "text": "yes, confirm"
}
```

### Expected response

- `conversation_state`: `CONFIRMED`
- `enquiry_id`: `ENQ-<12 hex chars>` (present for the first time)
- `quotation_status`: `CONFIRMED`
- A plain-text reply confirming the order and giving the enquiry reference.

### Step 3 — Repeat the same confirmation

Send the exact same request again (same `message_id`, `demo-2-1`).
## Scenario 3 — Missing quantity triggers clarification

**Goal:** Show the assistant asking for a quantity when the customer names a product but not how many.

### Step 4 — New customer, product only

```json
{
  "message_id": "demo-3-1",
  "sender_id": "demo-customer-b",
  "text": "I need wireless mice"
}
```

### Expected response

- `conversation_state`: `AWAITING_QUANTITY`
- Pending product remembered: Wireless Optical Mouse (MS-201)
- Plain-text reply asking: "How many units of Wireless Optical Mouse would you like to add?"

### Step 5 — Provide the quantity

```json
{
  "message_id": "demo-3-2",
  "sender_id": "demo-customer-b",
  "text": "3"
}
```

## Scenario 4 — Insufficient stock blocks quotation

**Goal:** Show stock validation before any enquiry is created.

### Step 6 — New customer, request more than available

KB-101 (Ergonomic Mechanical Keyboard) has stock 25 in `app/data/products.json`.

```json
{
  "message_id": "demo-4-1",
  "sender_id": "demo-customer-c",
  "text": "I need 30 Ergonomic Mechanical Keyboards"
}
```

### Expected response

- `is_unsupported`: `false`
- No `enquiry_id` created.
- `quotation_status`: remains `DRAFT` or no quotation created.
- Plain-text reply explaining insufficient stock, e.g.:
  ```text
  I cannot prepare a quotation for the following items:
  - Ergonomic Mechanical Keyboard (KB-101): insufficient stock (requested 30, available 25).
  No enquiry ID has been created. Please adjust quantities or choose other products.
  ```

### What to point out

- Stock is validated **before** any enquiry ID is created.
- Customer gets a specific, actionable message (which product, requested vs available).

## Scenario 5 — Human handoff for unsupported request

**Goal:** Show the assistant gracefully handing off requests it cannot handle.

### Step 7 — New customer, unsupported request

```json
{
  "message_id": "demo-5-1",
  "sender_id": "demo-customer-d",
  "text": "Can you order a pepperoni pizza for me?"
}
## Scenario 6 — Duplicate message_id protection (replay)

**Goal:** Show that replaying the exact same incoming event is rejected.

### Step 8 — Re-send any previous message_id

Pick any `message_id` already used (e.g. `demo-1-1`) and resend it with the same payload.

### Expected response

- `duplicated`: `true`
- No state change, no new cart item, no new enquiry.

### What to point out

- Exactly-once processing for webhook-style events.
- Protects against network retries and accidental double-sends.

## Quick reference — all scenario message_ids

| Scenario | sender_id | message_id(s) |
|---|---|---|
| 1. Multi-product quote | demo-customer-a | demo-1-1 |
| 2. Confirm + duplicate | demo-customer-a | demo-2-1 (twice) |
| 3. Clarification flow | demo-customer-b | demo-3-1, demo-3-2 |
| 4. Insufficient stock | demo-customer-c | demo-4-1 |
| 5. Human handoff | demo-customer-d | demo-5-1 |
| 6. Duplicate replay | (any previous) | reuse any earlier message_id |

## What the demo proves end-to-end

1. Natural-language product + quantity extraction.
2. Per-sender cart and conversation state.
3. Draft quotation with Decimal-precision tax/totals.
4. Explicit confirmation before enquiry creation.
5. Stock validation before enquiry.
6. Human handoff for out-of-domain requests.
7. Duplicate `message_id` protection / idempotency.
8. Persistence across sender sessions (SQLite).
```

### Expected response

- `is_unsupported`: `true`
- Plain-text reply explaining the request is out of scope and has been passed to a human, e.g.:
  ```text
  I'm sorry, I'm unable to help with that request. This has been passed to our human sales team for assistance. They will get back to you shortly.
  Reference: your message has been logged for review.
  ```
- A `HandoffModel` record is persisted with conversation context.

### What to point out

- Unsupported intents never create quotations or enquiries.
- The handoff is persisted so a human reviewer can follow up.
### Expected response

- `conversation_state`: `AWAITING_CONFIRMATION`
- Cart now contains Wireless Optical Mouse × 3
- Draft quotation with line totals and tax
- Plain-text reply summarising the draft and asking to confirm.

### What to point out

- State machine remembers the pending product across messages from the same sender.
- Written numbers ("three") also work (see test `test_4_follow_up_with_written_number_word`).

### Expected response

- `duplicated`: `true`
- `enquiry_id`: unchanged — still the same `ENQ-<...>` from step 2.
- No second enquiry created.

### What to point out

- Explicit confirmation gate: no enquiry until "yes".
- Idempotency: duplicate `message_id` is rejected; no duplicate enquiries.

### Expected response

- `intent`: `quotation_request`
- `conversation_state`: `AWAITING_CONFIRMATION`
- Cart contains Wireless Optical Mouse (MS-201) × 2 and Ergonomic Mechanical Keyboard (KB-101) × 1
- `quotation_status`: `DRAFT`
- `enquiry_id`: `null` (not yet confirmed)
- A plain-text reply summarising the draft quotation and asking the customer to confirm.

### What to point out

- One message, two products, quantities parsed correctly.
- Draft quotation created with tax; no enquiry ID yet — confirmation is still pending.