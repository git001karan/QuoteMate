# PS05 Assessment Compliance Audit — QuoteMate

**Project:** QuoteMate — WhatsApp Sales and Quotation Assistant
**Assessment:** Cerevyn Solutions PS05 Software Engineering
**Date:** 2026-10-17
**Test Suite Result:** 80 passed, 1 warning (`pytest tests/`)

---

## Requirement Audit Summary

| # | Requirement | Status | Implementation Location | Verification Method |
|---|-------------|--------|-------------------------|---------------------|
| 1 | Product catalogue (10+ products with ID, description, price, stock) | PASS | `app/data/products.json`, `app/services/catalogue_service.py`, `app/models.py` (`ProductModel`) | `tests/test_products.py::test_catalogue_contains_at_least_10_products`, `test_each_product_has_required_fields`, `test_product_ids_are_unique` |
| 2 | Incoming message events (message ID, sender ID, timestamp, text) | PASS | `app/schemas.py` (`IncomingMessage`), `app/models.py` (`MessageModel`) | `tests/test_database.py::test_7_duplicate_message_ids_rejected`, `test_conversation_cart.py::test_12_duplicate_message_id_rejected_and_idempotent` |
| 3 | NLP intent/product interpretation with missing-info handling | PASS | `app/services/nlp_service.py` | `tests/test_nlp.py` (15 tests) |
| 4 | Independent carts and conversation state per sender | PASS | `app/services/cart_service.py`, `app/services/conversation_service.py` | `tests/test_conversation_cart.py::test_1_separate_customers_have_independent_conversations_and_carts` |
| 5 | Accurate line totals, configured tax, final quotation amounts | PASS | `app/services/quotation_service.py` | `tests/test_quotation.py::test_1_line_totals_and_subtotal_for_multiple_products`, `test_2_configured_tax_and_final_total`, `test_3_monetary_rounding_and_decimal_precision` |
| 6 | Clear handling of unavailable products and insufficient stock | PASS | `app/services/quotation_service.py` (`StockIssue`) | `tests/test_quotation.py::test_4_unknown_or_unavailable_products`, `test_5_insufficient_stock` |
| 7 | Enquiry ID created only after successful customer confirmation | PASS | `app/services/quotation_service.py` (`confirm_for_sender()`) | `tests/test_quotation.py::test_6_no_enquiry_id_before_customer_confirmation`, `test_7_successful_confirmation_creates_exactly_one_enquiry_id` |
| 8 | Human handoff for unsupported requests with context | PASS | `app/services/handoff_service.py`, `app/services/message_service.py` | `tests/test_handoff.py` (8 tests) |

---

## Detailed Requirement Analysis

### Requirement 1: Product Catalogue (≥10 products) — PASS

**Implementation:** `app/data/products.json` contains 12 products with `id`, `name`, `description`, `price`, `stock`. `app/services/catalogue_service.py::CatalogueService` seeds products into SQLite. `app/models.py::ProductModel` defines `id` (PK), `name`, `description`, `price` (Numeric 10,2), `stock` (Integer, check `stock >= 0`). API: `GET /products` and `GET /products/{product_id}` in `app/api/routes.py`.

**Tests:** `tests/test_products.py::test_catalogue_contains_at_least_10_products`, `test_each_product_has_required_fields`, `test_product_ids_are_unique`, `test_list_products_returns_200`, `test_get_existing_product_returns_correct_details`, `test_get_unknown_product_returns_404`.

**Evidence:** All tests pass. Catalogue has 12 products (≥10 required).

### Requirement 2: Incoming Message Events — PASS

**Implementation:** `app/schemas.py::IncomingMessage` has `message_id`, `sender_id`, `text`, `timestamp`. `app/models.py::MessageModel` persists these with `message_id` (unique). API: `POST /webhook` and `POST /messages` in `app/api/routes.py`.

**Tests:** `tests/test_database.py::test_7_duplicate_message_ids_rejected`, `tests/test_conversation_cart.py::test_12_duplicate_message_id_rejected_and_idempotent`.

### Requirement 3: NLP Intent/Product Interpretation — PASS

**Implementation:** `app/services/nlp_service.py::NLPService` — TF-IDF + LogisticRegression classifier, RapidFuzz product matching, quantity extraction (digits and written words). Intents: `product_inquiry`, `quotation_request`, `confirmation`, `decline`, `general_question`, `unsupported`. Flags: `needs_clarification`, `is_unsupported`, `has_missing_quantities`, `clarification_reason`.

**Tests:** `tests/test_nlp.py` — 15 tests covering all NLP aspects, including regression tests verifying that a generic shared word (e.g. 'wireless') cannot independently justify a cross-category product match.

### Requirement 8: Human Handoff for Unsupported Requests — PASS

**Implementation:** `app/services/handoff_service.py::HandoffService` — `create_handoff()` with duplicate prevention (one PENDING per sender). `app/services/message_service.py` unsupported intent branch creates handoff with context (latest message, reason, conversation state, cart, quotation). Returns simulated response; never claims real agent contact.

**API:** `GET /handoffs/{sender_id}` in `app/api/routes.py`.

**Tests:** `tests/test_handoff.py` — 8 tests covering creation, context, response, no-handoff-for-clarification, duplicate prevention, isolation, no-quotation-creation, persistence.

### Requirement 9: Duplicate Message ID Protection — PASS

**Implementation:** `app/services/message_service.py::process_incoming_message()` checks `MessageModel.message_id` uniqueness before processing. Returns `duplicated=True` with cached response on replay. `IntegrityError` handler for concurrent races.

**Tests:** `tests/test_conversation_cart.py::test_12_duplicate_message_id_rejected_and_idempotent`, `tests/test_database.py::test_7_duplicate_message_ids_rejected`.

### Requirement 10: Persistence and Simulated Outgoing Messages — PASS

**Implementation:** SQLAlchemy models + SQLite via `app/database.py`. All state (conversations, carts, quotations, handoffs, messages) persisted. `ProcessedMessageReply.reply_text` contains the simulated assistant message. Cross-session persistence verified.

**Tests:** `tests/test_quotation.py::test_13_draft_and_confirmed_quotations_persist_across_sessions`, `tests/test_conversation_cart.py::test_13_state_and_cart_persistence_across_sessions`.

### Requirement 11: Automated Tests — PASS

**Implementation:** 80 tests across 7 files: `test_conversation_cart.py` (16), `test_database.py` (10), `test_health.py` (2), `test_nlp.py` (15), `test_products.py` (13), `test_quotation.py` (14), `test_handoff.py` (8).

**Result:** 80 passed, 1 warning (httpx/testclient deprecation, not a failure).

### Requirement 12: Documented Azure Deployment Plan — NOT VERIFIED

**Finding:** No `docs/azure-deployment.md` or any deployment documentation exists in the repository.

**Gap:** The assessment requires a documented Azure deployment plan, but none exists.

**Recommended fix:** Create `docs/azure-deployment.md` documenting deployment architecture, ARM/Bicep templates, environment variables, and CI/CD steps.

---

## Remaining Gaps and Recommended Fixes

| Gap | Requirement | Recommended Fix |
|-----|-------------|-----------------|
| No Azure deployment documentation | #12 | Create `docs/azure-deployment.md` with deployment architecture, ARM/Bicep templates, environment variables, and CI/CD steps |

---

## Test Coverage Summary

| Test File | Tests | Areas Covered |
|-----------|-------|---------------|
| `tests/test_conversation_cart.py` | 16 | Cart management, conversation states, duplicate handling, persistence, webhook endpoints, generic-token cross-match regression |
| `tests/test_database.py` | 10 | Table creation, seeding, idempotency, FK constraints, message duplicates |
| `tests/test_health.py` | 2 | Root endpoint, health check |
| `tests/test_nlp.py` | 15 | Intent classification, product matching, quantity extraction, structured output, generic-token cross-match regression |
| `tests/test_products.py` | 13 | Catalogue size, required fields, unique IDs, API endpoints, schema validation |
| `tests/test_quotation.py` | 14 | Line totals, tax, rounding, stock issues, enquiry lifecycle, confirmation, isolation, persistence |
| `tests/test_handoff.py` | 8 | Handoff creation, context, response, no-handoff clarification, duplicates, isolation, no-quote, persistence |
| **Total** | **80** | All Milestones 1-7 covered |

---

## Conclusion

**11 of 12 requirements are PASS.** Requirement 12 (Azure deployment documentation) is NOT VERIFIED — no deployment documentation exists. All functional requirements are implemented and verified by the automated test suite (80 passed, 0 failed).


### Requirement 4: Independent Carts and Conversation State — PASS

**Implementation:** `app/services/cart_service.py::CartService` and `app/services/conversation_service.py::ConversationService`, keyed by `sender_id`. `CartItemModel` has `sender_id` + `product_id` unique constraint. `ConversationModel` has `sender_id` unique.

**Tests:** `tests/test_conversation_cart.py::test_1_separate_customers_have_independent_conversations_and_carts`, `tests/test_quotation.py::test_12_customers_cannot_access_or_confirm_each_others_quotations`.

### Requirement 5: Accurate Line Totals, Tax, Final Amounts — PASS

**Implementation:** `app/services/quotation_service.py` — `money()` uses `Decimal` with `ROUND_HALF_UP` to `0.01`. `configured_tax_rate()` reads `DEFAULT_TAX_RATE` (0.18). `evaluate_items()` computes line_total = unit_price × quantity, subtotal = sum, tax_amount = subtotal × tax_rate, total = subtotal + tax_amount.

**Tests:** `tests/test_quotation.py::test_1_line_totals_and_subtotal_for_multiple_products`, `test_2_configured_tax_and_final_total`, `test_3_monetary_rounding_and_decimal_precision`.

### Requirement 6: Unavailable Products and Insufficient Stock — PASS

**Implementation:** `app/services/quotation_service.py::evaluate_items()` checks product existence (`unknown`), stock > 0 (`unavailable`), quantity <= stock (`insufficient_stock`). Returns `StockIssue` list with reason and requested vs available quantities. No quotation/enquiry created when issues exist.

**Tests:** `tests/test_quotation.py::test_4_unknown_or_unavailable_products`, `test_5_insufficient_stock`.

### Requirement 7: Enquiry ID Only After Confirmation — PASS

**Implementation:** `app/services/quotation_service.py::confirm_for_sender()` revalidates stock/prices, sets `status=CONFIRMED`, assigns `enquiry_id` only after successful revalidation. Drafts have `enquiry_id=None`. Unique DB constraint on `enquiry_id`.

**Tests:** `tests/test_quotation.py::test_6_no_enquiry_id_before_customer_confirmation`, `test_7_successful_confirmation_creates_exactly_one_enquiry_id`, `test_8_decline_does_not_create_confirmed_enquiry`, `test_9_repeated_confirmation_does_not_create_duplicate_enquiries`.

| 9 | Duplicate message ID protection | PASS | `app/services/message_service.py` | `tests/test_conversation_cart.py::test_12_duplicate_message_id_rejected_and_idempotent` |
| 10 | Persistence of conversations and quotations | PASS | `app/database.py`, `app/models.py` | `tests/test_quotation.py::test_13_draft_and_confirmed_quotations_persist_across_sessions` |
| 11 | Automated tests for required assessment scenarios | PASS | `tests/test_*.py` (80 tests) | Full suite: `pytest tests/` → 80 passed |
| 12 | Documented Azure deployment plan | NOT VERIFIED | None found | No deployment documentation exists |
