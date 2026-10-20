# QuoteMate — Scenario Test Mapping

This document maps ≥5 end-to-end demo scenarios to the automated test suite that covers them. Every scenario in `sample_data/events.json` is exercised by `scripts/demo.py` (wired into `tests/test_demo_replay.py`) and/or by dedicated pytest unit tests.

| # | Scenario (from `events.json`) | Automated test coverage | Test file |
|---|-------------------------------|------------------------|-----------|
| 1 | **Multi-product quote** — customer requests multiple products with quantities in one message | `test_1` multi-product quote; `test_demo_replay` demo-1 | `tests/test_conversation_cart.py::test_8_multiple_products_added_in_single_message`; `tests/test_demo_replay.py` |
| 2 | **Missing quantity** — product named without quantity triggers clarification; follow-up quantity completes the request | `test_2` missing quantity follow-up; `test_demo_replay` demo-2 | `tests/test_conversation_cart.py::test_2_missing_quantity_triggers_follow_up_and_remembers_product`; `tests/test_demo_replay.py` |
| 3 | **Insufficient stock** — request exceeds available stock; stock validated before enquiry creation | `test_5` insufficient stock; `test_demo_replay` demo-3 | `tests/test_quotation.py::test_5_insufficient_stock`; `tests/test_demo_replay.py` |
| 4 | **Duplicate event** — same `message_id` replayed is rejected idempotently | `test_12` duplicate message rejected; `test_demo_replay` demo-4 | `tests/test_conversation_cart.py::test_12_duplicate_message_id_rejected_and_idempotent`; `tests/test_demo_replay.py` |
| 5 | **Two independent users** — separate senders have independent carts/conversations | `test_1` separate customers | `tests/test_conversation_cart.py::test_1_separate_customers_have_independent_conversations_and_carts` |
| 6 | **Human handoff** — unsupported request creates persisted handoff record | `test_handoff_unsupported`; `test_demo_replay` demo-6 | `tests/test_handoff.py::test_unsupported_intent_creates_persisted_handoff`; `tests/test_demo_replay.py` |
| 7 | **Invalid input** — empty `message_id` rejected with HTTP 422 | `test_demo_replay` demo-7; schema validation tests | `tests/test_demo_replay.py`; `tests/test_products.py::test_schema_rejects_invalid_values*` |
| 8 | **Typo-tolerant NLP** — Hinglish/typo queries classify correctly | `test_22`, `test_23` typo tolerance | `tests/test_nlp.py::test_22_typo_tolerant_product_inquiry`; `tests/test_nlp.py::test_23_typo_tolerant_quotation_request` |
| 9 | **Paraphrase NLP** — paraphrased product/quotation requests classify correctly | `test_24`, `test_25` paraphrase | `tests/test_nlp.py::test_24_paraphrase_product_inquiry`; `tests/test_nlp.py::test_25_paraphrase_quotation_request` |

## NLP evaluation results

| Dataset | Size | Accuracy | Source |
|---------|------|----------|--------|
| Dev evaluation split (inside `messages_dataset.json`) | 24 | 91.67% | `nlp_service.evaluate()` |
| Held-out novelty set (`novelty_test.json`) | 40 | 72.50% | `nlp_service.evaluate(dataset_path="sample_data/novelty_test.json")` |

Full metrics (including per-class precision/recall/F1 and confusion matrices) are stored in `sample_data/nlp_evaluation_results.json` and summarised honestly in `README.md`.

## How to run

```powershell
# Backend unit tests (80+ tests)
.venv\Scripts\python.exe -m pytest tests/ -v

# With coverage
.venv\Scripts\python.exe -m pytest tests/ --cov=app --cov-report=term

# Demo replay (events.json vs expected_outputs.json)
.venv\Scripts\python.exe scripts/demo.py

# Full CI-equivalent (lint + tests + coverage)
.venv\Scripts\python.exe -m ruff check app/ scripts/ tests/
.venv\Scripts\python.exe -m pytest tests/ --cov=app --cov-report=term --cov-report=xml
```

## CI mapping

| CI job | What it validates |
|--------|-------------------|
| `lint` | `ruff check app/ scripts/ tests/` — zero lint errors |
| `test` | `pytest tests/ --cov=app` — all tests pass, coverage XML uploaded |
| `node` | Frontend `npm ci` + `npm run build` |
| `docker-build` | `docker build --tag quotemate:ci .` — image builds, tar uploaded |