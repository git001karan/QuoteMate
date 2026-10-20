# QuoteMate — Demo Script (Milestone 11)

**Project:** QuoteMate — AI-Powered WhatsApp Sales and Quotation Assistant  
**Assessment:** Cerevyn Solutions PS05  
**Purpose:** A timed 3–5 minute live demo script walking through the core customer-facing flows. Each scenario shows what to type (simulated via `POST /messages`) and what the assistant replies.  
**Automation:** Scenarios 1–6 replay the events in `sample_data/events.json` that `scripts/demo.py` verifies against `sample_data/expected_outputs.json` (run `python scripts/demo.py` — 11 checks, all passing). This includes the explicit-confirmation step: the replay asserts that no `ENQ-` ID appears before the customer confirms, and that the confirmation reply matches `^ENQ-[0-9A-F]{12}$`.

---

## How to run the live demo

1. Activate the virtual environment:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

2. Start the server:

   ```powershell
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

3. Send each request as `POST /messages`:

   ```bash
   curl -X POST http://127.0.0.1:8000/messages \
     -H "Content-Type: application/json" \
     -d '{"message_id":"<UNIQUE_ID>","sender_id":"<CUSTOMER_ID>","text":"<MESSAGE>"}'
   ```

4. Use a fresh `sender_id` per scenario unless the scenario explicitly continues a previous conversation. The IDs below match `sample_data/events.json`, so you can copy-paste them verbatim.

### Reset the database before every rehearsal (required)

The live server stores every processed `message_id` in a persistent SQLite file (`quotemate.db`) for idempotency, and a confirmation decrements stock. Rehearsing twice against the same file would return `"duplicated": true` for every message and show stock already reduced — which looks broken on camera. **Delete the database and restart the server before each rehearsal:**

```powershell
# 1. Stop the server (Ctrl+C), then:
Remove-Item .\quotemate.db -ErrorAction SilentlyContinue
# 2. Start it again — the lifespan hook re-creates and re-seeds the catalogue:
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

After the reset, stock is back to its seeded values (MS-201 = 60, HP-302 = 35) and no `message_id` is taken, so every rehearsal starts identical. (`scripts/demo.py` needs no reset — it runs against a throwaway tmp database each time.)

---

## Timing plan (3–5 minutes)

| Segment | Time |
|---------|------|
| Introduction | 0:30 |
| Scenario 1 — Multi-product quotation + confirmation | 1:15 |
| Scenario 2 — Missing quantity clarification | 0:45 |
| Scenario 3 — Insufficient stock | 0:30 |
| Scenario 4 — Duplicate message_id protection | 0:30 |
| Scenario 5 — Independent customers (separate carts) | 0:30 |
| Scenario 6 — Human handoff for out-of-domain request | 0:30 |
| Conclusion & Q&A | 0:30 |
| **Total** | **~4:30–5:00** |

---

## Introduction (0:30)

Say: "QuoteMate is an AI-powered WhatsApp sales assistant for PS05. It understands natural-language product enquiries, collects quantities, keeps one cart per customer, calculates quotations with tax, asks for explicit confirmation before creating an enquiry, blocks over-stock requests, and hands unexpected requests to a human. Let me walk you through six scenarios."

---

## Scenario 1 — Multi-product quotation, then explicit confirmation (1:15)

**Goal:** Natural-language extraction of multiple products + quantities, a draft quotation, then an explicit confirmation that creates exactly one enquiry ID.

### Step A — Multi-product request (`event: demo-1-multi-product-quote`)

```json
{
  "message_id": "msg_alice_001",
  "sender_id": "user_alice",
  "text": "2 wireless mice and 1 headset"
}
```

**Expected response (verified by demo.py):**
- `intent`: `quotation_request`
- `conversation_state`: `AWAITING_CONFIRMATION`
- `enquiry_id`: `null` — **no enquiry ID exists yet** (also asserted by the replay: the reply must not contain `ENQ-`)
- Cart contains MS-201 (Wireless Optical Mouse) × 2 and HP-302 (Lightweight Wired Gaming Headset) × 1
- Reply prints the quotation arithmetic — **these exact numbers are asserted by `demo.py`**:

  ```text
  1. Lightweight Wired Gaming Headset (HP-302) x 1 @ Rs 2,199.00 = Rs 2,199.00
  2. Wireless Optical Mouse (MS-201) x 2 @ Rs 799.00 = Rs 1,598.00
  Subtotal: Rs 3,797.00
  Tax (18%): Rs 683.46
  Total: Rs 4,480.46
  ```

  Arithmetic: (1 × 2,199) + (2 × 799) = 3,797 · 3,797 × 18% = 683.46 · 3,797 + 683.46 = **4,480.46**.

### Step B — Explicit confirmation (new `message_id`, same `sender_id`)

```json
{
  "message_id": "msg_alice_002",
  "sender_id": "user_alice",
  "text": "yes, confirm"
}
```

**Expected response (verified by demo.py):**
- `conversation_state`: `CONFIRMED`
- `enquiry_id`: matches `^ENQ-[0-9A-F]{12}$` — present for the first time (the replay asserts this regex, since the 12 hex chars are random)
- `quotation_status`: `CONFIRMED`
- Reply: "Thank you! Your quotation has been confirmed. ... Enquiry ID: ENQ-... ... Our sales team will follow up using this enquiry ID."
- The draft in Step A asserted `enquiry_id: null` (no `ENQ-` in the reply); this step asserts the ID now exists — together they prove **the enquiry ID is created only on confirmation**.

**What to point out:** "One message, two products, quantities parsed correctly, draft quotation with 18% tax. No enquiry ID yet — only after the customer says 'yes' does the assistant create exactly one `ENQ-...` reference, and stock is now decremented. Re-confirming never duplicates it (covered by `tests/test_quotation.py::test_9`)."

---

## Scenario 2 — Missing quantity triggers clarification (0:45)

**Goal:** The assistant asks for a quantity when the customer names a product but not how many, then remembers the pending product across messages from the same sender.

### Step A — Product only (`event: demo-2-missing-quantity`)

```json
{
  "message_id": "msg_bob_001",
  "sender_id": "user_bob",
  "text": "I want a webcam"
}
```

**Expected response (verified by demo.py):**
- `needs_clarification`: `true`
- `conversation_state`: `AWAITING_QUANTITY`
- Cart is still empty (nothing added yet)
- Reply asks for a quantity (mentions the webcam and how many units).

### Step B — Provide the quantity (new `message_id`, same `sender_id`)

```json
{
  "message_id": "msg_bob_002",
  "sender_id": "user_bob",
  "text": "2 please"
}
```

**Expected response (verified by demo.py):**
- `conversation_state`: `AWAITING_CONFIRMATION`
- Cart now contains WC-501 (1080p Full HD Pro Webcam) × 2
- Draft quotation reply (contains WC-501 and the rupee amount).

**What to point out:** "The state machine remembers the pending product across messages from the same sender — the customer does not repeat the product name. Nothing enters the cart until the quantity is known."

---

## Scenario 3 — Insufficient stock is flagged (0:30)

**Goal:** Stock is validated against the catalogue before a quotation is finalised; over-stock requests are flagged so the customer can adjust.

### Step — Request more than available (`event: demo-3-insufficient-stock`)

MS-201 (Wireless Optical Mouse) has stock **60 when seeded** in `app/data/products.json` — but see the stock note below: after Scenario 1's confirmation it is 58 at this point in the run.

```json
{
  "message_id": "msg_charlie_001",
  "sender_id": "user_charlie",
  "text": "70 wireless mice"
}
```

**Expected response (verified by demo.py):**
- `intent`: `quotation_request`
- `needs_clarification`: `true` — the assistant flags the stock problem
- Cart contains MS-201, but the quotation is invalid — no enquiry ID is created
- Reply reports the live shortfall: **`insufficient stock (requested 70, available 58)`** — the replay asserts both the word "stock" and the count.

> **Stock note (order dependence):** the count is **58, not 60**, because this scenario runs *after* Scenario 1's confirmation decremented MS-201 by 2 (60 − 2 = 58). That is the point — confirmation really reduces live stock and Scenario 3 re-reads it. A [database reset](#reset-the-database-before-every-rehearsal-required) restores 60, so **rehearse in order from a fresh reset**, and quote whatever number the reply actually shows (58 in a full run; 60 if you demo this scenario alone immediately after a reset).

**What to point out:** "The assistant checks live catalogue stock — not a cached value. Requesting 70 triggers a clarification so the customer can correct the quantity, and no quotation or enquiry ID is produced. It will not silently over-promise inventory."

---

## Scenario 4 — Duplicate message_id protection (0:30)

**Goal:** Replaying the exact same incoming event is rejected idempotently — exactly-once processing for webhook-style retries.

### Step A — First delivery (`event: demo-4-duplicate-event`)

```json
{
  "message_id": "msg_dave_001",
  "sender_id": "user_dave",
  "text": "quote for 4 webcams"
}
```

**Expected response (verified by demo.py):**
- `duplicated`: `false`
- `conversation_state`: `AWAITING_CONFIRMATION`
- Cart contains WC-501 × 4; draft quotation reply (WC-501 + rupee amount).

### Step B — Exact replay (identical `message_id`, `sender_id`, and `text`)

Send the identical payload again.

**Expected response (verified by demo.py):**
- `duplicated`: `true`
- The stored reply is replayed; no second cart update, no second quotation.

**What to point out:** "Exactly-once processing protects against network retries and accidental double-sends — critical for WhatsApp webhook delivery, where a message may be delivered more than once."

---

## Scenario 5 — Independent customers keep separate carts (0:30)

**Goal:** Two different senders never share state — each `sender_id` has its own cart and conversation.

### Step A — First customer (`event: demo-5-two-independent-users`)

```json
{
  "message_id": "msg_eve_001",
  "sender_id": "user_eve",
  "text": "1 mechanical keyboard"
}
```

**Expected response (verified by demo.py):**
- Cart for `user_eve` contains KB-101 (Ergonomic Mechanical Keyboard) × 1; reply mentions KB-101.

### Step B — Second customer (`event: demo-5b-second-user`)

```json
{
  "message_id": "msg_frank_001",
  "sender_id": "user_frank",
  "text": "3 laptop stands please"
}
```

**Expected response (verified by demo.py):**
- Cart for `user_frank` contains LP-801 (Adjustable Aluminum Laptop Stand) × 3; reply mentions LP-801.
- `user_eve`'s cart is untouched by `user_frank`'s message.

**What to point out:** "Carts and conversation state are keyed by `sender_id`. Two customers messaging at the same time never see or modify each other's items."

---

## Scenario 6 — Human handoff for out-of-domain request (0:30)

**Goal:** Requests outside the sales domain create a persisted human handoff record instead of a quotation.

### Step — Unsupported request (`event: demo-6-handoff`)

```json
{
  "message_id": "msg_grace_001",
  "sender_id": "user_grace",
  "text": "can you invest in my startup"
}
```

**Expected response (verified by demo.py):**
- `intent`: `unsupported`
- `is_unsupported`: `true`
- `handoff_id`: an integer (a `HandoffModel` row is persisted with conversation context)
- No `enquiry_id`; no quotation created
- Reply explains the request is out of scope and has been passed to the human sales team (contains "human" and "team").

**What to point out:** "Out-of-domain requests never produce quotations. The handoff is persisted with full conversation context, so a human reviewer can follow up. Agents can resolve it via `POST /handoffs/{id}/resolve`."

### Bonus — Input validation (`event: demo-7-invalid-input`)

```json
{
  "message_id": "",
  "sender_id": "user_heidi",
  "text": "hello"
}
```

**Expected response (verified by demo.py):** HTTP `422` — an empty `message_id` is rejected by schema validation before any processing.

---

## Conclusion (0:30)

Say: "That's QuoteMate — six scenarios in under five minutes: natural-language parsing, per-customer carts, draft quotations with tax, explicit confirmation creating exactly one enquiry ID, live stock validation, human handoff for out-of-domain requests, and duplicate-message protection. Every scenario you just saw is replayed and asserted by `scripts/demo.py` on every CI run."

---

## Quick reference — all scenario IDs (from `sample_data/events.json`)

| Scenario | event_id | sender_id | message_id(s) |
|----------|----------|-----------|---------------|
| 1. Multi-product + confirm | demo-1-multi-product-quote | user_alice | msg_alice_001 (+ msg_alice_002 to confirm) |
| 2. Missing quantity | demo-2-missing-quantity | user_bob | msg_bob_001, msg_bob_002 |
| 3. Insufficient stock | demo-3-insufficient-stock | user_charlie | msg_charlie_001 |
| 4. Duplicate replay | demo-4-duplicate-event | user_dave | msg_dave_001 (sent twice) |
| 5. Independent carts | demo-5 / demo-5b | user_eve, user_frank | msg_eve_001, msg_frank_001 |
| 6. Human handoff | demo-6-handoff | user_grace | msg_grace_001 |
| Bonus — invalid input | demo-7-invalid-input | user_heidi | "" (empty → 422) |

---

## What the demo proves end-to-end

1. Natural-language product + quantity extraction (multiple items in one message).
2. Per-sender cart and conversation state — no cross-customer leakage.
3. Draft quotation with Decimal-precision tax/totals (18% default).
4. Explicit confirmation gate — exactly one `ENQ-<12 hex>` enquiry ID, only on "yes".
5. Live stock validation before a quotation is finalised.
6. Human handoff for out-of-domain requests, persisted for follow-up.
7. Duplicate `message_id` protection / idempotent webhook processing.
8. Schema validation rejects malformed input (422).
9. Persistence across sender sessions (SQLite).
