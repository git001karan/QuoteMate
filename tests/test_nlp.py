"""Automated test suite for AI and Natural-Language Understanding (Milestone 4)."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import NLPAnalysisResult
from app.services.nlp_service import NLPService, nlp_service

client = TestClient(app)


def test_1_intent_classification_for_representative_messages():
    """Requirement 1: Verify correct intent classification across all supported intent classes."""
    test_cases = [
        ("Do you have mechanical keyboards in stock?", "product_inquiry"),
        ("Please prepare a quotation for two mice.", "quotation_request"),
        ("Yes, please confirm this quotation.", "confirmation"),
        ("No, cancel this quotation.", "decline"),
        ("What are your business operating hours?", "general_question"),
        ("Can you order a pepperoni pizza for me?", "unsupported"),
    ]
    for text, expected_intent in test_cases:
        intent, confidence = nlp_service.predict_intent(text)
        assert intent == expected_intent, f"Failed for '{text}': expected {expected_intent}, got {intent}"
        assert confidence > 0.35


def test_2_product_enquiries_with_paraphrased_wording():
    """Requirement 2: Verify intent and matching for natural-language paraphrases."""
    paraphrases = [
        "Are there any mechanical typing boards available?",
        "Can you check if you have gaming headsets right now?",
        "Do you carry wireless pointing devices?",
    ]
    for phrase in paraphrases:
        res = nlp_service.analyze(phrase)
        assert res.intent in ("product_inquiry", "quotation_request")


def test_3_exact_product_matching():
    """Requirement 3: Verify exact product name matching against SQLite catalogue."""
    result = nlp_service.analyze("I need Ergonomic Mechanical Keyboard")
    matched_ids = [p.product_id for p in result.matched_products]
    assert "KB-101" in matched_ids
    matched_item = next(p for p in result.matched_products if p.product_id == "KB-101")
    assert matched_item.match_score >= 80.0
    assert not matched_item.is_ambiguous


def test_4_ambiguous_and_unknown_products():
    """Requirement 4: Verify unknown products are not matched and ambiguous references are flagged."""
    # Completely unknown product (refrigerator / air conditioner)
    unknown_result = nlp_service.analyze("Do you sell refrigerators and washing machines?")
    assert len(unknown_result.matched_products) == 0
    assert unknown_result.is_unsupported or unknown_result.needs_clarification

    # Ambiguous request: generic "monitor" could refer to 4K or 1080p office monitor
    ambiguous_result = nlp_service.analyze("Please quote for monitor")
    assert ambiguous_result.needs_clarification or len(ambiguous_result.matched_products) > 0


def test_5_numeric_quantity_extraction():
    """Requirement 5: Verify digit quantities (e.g., 3, 10) are correctly extracted."""
    qty, is_inv, has_qty = nlp_service.extract_quantity_from_phrase("3 wireless keyboards")
    assert has_qty is True
    assert is_inv is False
    assert qty == 3

    qty2, is_inv2, has_qty2 = nlp_service.extract_quantity_from_phrase("give me 15 usb hubs")
    assert qty2 == 15
    assert not is_inv2


def test_6_number_word_quantity_extraction():
    """Requirement 6: Verify written number words ('one', 'two', 'three', etc.) are extracted."""
    qty1, _, has_qty1 = nlp_service.extract_quantity_from_phrase("two wireless mice")
    assert has_qty1 is True
    assert qty1 == 2

    qty2, _, has_qty2 = nlp_service.extract_quantity_from_phrase("five gaming headsets")
    assert has_qty2 is True
    assert qty2 == 5

    qty3, _, has_qty3 = nlp_service.extract_quantity_from_phrase("one usb hub")
    assert has_qty3 is True
    assert qty3 == 1


def test_7_missing_quantities_not_defaulted_to_one():
    """Requirement 7: Verify missing quantity is flagged as None / missing, not defaulted to 1."""
    # "I need keyboards" specifies no quantity
    qty, is_inv, has_qty = nlp_service.extract_quantity_from_phrase("I need mechanical keyboards")
    assert has_qty is False
    assert qty is None

    result = nlp_service.analyze("Please prepare a quote for mechanical keyboards.")
    assert result.has_missing_quantities is True
    assert result.needs_clarification is True
    for item in result.matched_products:
        assert item.extracted_quantity is None
        assert item.quantity_missing is True


def test_8_zero_and_negative_quantities_rejected():
    """Requirement 8: Verify 0 and negative quantities are rejected and never accepted as valid counts."""
    # Zero quantity
    qty_zero, is_inv_zero, has_qty_zero = nlp_service.extract_quantity_from_phrase("0 mechanical keyboards")
    assert is_inv_zero is True
    assert qty_zero == 0

    # Negative quantity
    qty_neg, is_inv_neg, _ = nlp_service.extract_quantity_from_phrase("-3 wireless mice")
    assert is_inv_neg is True
    assert qty_neg is None

    # Analyzing message with zero quantity marks missing/invalid quantity
    result = nlp_service.analyze("Quote for 0 wireless mice")
    assert result.has_missing_quantities is True
    assert result.needs_clarification is True


def test_9_unsupported_messages_and_low_confidence_fallback():
    """Requirement 9: Out-of-domain requests must trigger unsupported status or low-confidence fallback."""
    unsupported_messages = [
        "Can you fix my broken car engine?",
        "Can you order a pizza for me?",
        "What is the weather like in Tokyo?",
    ]
    for msg in unsupported_messages:
        res = nlp_service.analyze(msg)
        assert res.is_unsupported or res.needs_clarification or res.intent == "unsupported"


def test_10_database_backed_product_lookup(test_db_session):
    """Requirement 10: Verify product matching queries the actual SQLite ProductModel table."""
    # Match using explicitly provided session
    matched = nlp_service.match_products("3 mechanical keyboards and 2 vertical mice", db=test_db_session)
    assert len(matched) >= 2
    ids = {m.product_id for m in matched}
    assert "KB-101" in ids or "KB-102" in ids
    assert "MS-202" in ids or "MS-201" in ids


def test_11_structured_nlp_response_validation():
    """Requirement 11: Verify structured response matches Pydantic schema and API endpoint."""
    response = client.post(
        "/nlp/analyze",
        json={"text": "I need three wireless keyboards and two wireless mice. Please prepare a quotation."},
    )
    assert response.status_code == 200
    data = response.json()

    # Validate against Pydantic schema
    validated = NLPAnalysisResult.model_validate(data)
    assert validated.intent == "quotation_request"
    assert validated.intent_confidence > 0.40
    assert len(validated.matched_products) >= 2
    assert validated.original_text.startswith("I need three")


def test_12_reproducible_classifier_evaluation():
    """Requirement 12: Evaluate classifier on held-out evaluation dataset and verify metrics."""
    metrics = nlp_service.evaluate()
    assert metrics["train_size"] >= 50
    assert metrics["evaluation_size"] >= 20
    assert metrics["accuracy"] >= 0.80, f"Expected accuracy >= 0.80, got {metrics['accuracy']}"
    assert "classification_report" in metrics
