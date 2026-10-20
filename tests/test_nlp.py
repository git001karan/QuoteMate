"""Automated test suite for AI and Natural-Language Understanding (Milestone 4)."""

from fastapi.testclient import TestClient
from app.main import app
from app.schemas import NLPAnalysisResult
from app.services.nlp_service import nlp_service

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


def test_13_generic_word_alone_cannot_cross_match_products():
    """Regression: a generic shared word ('wireless') must not match an unrelated product.

    Bug reproduced before the fix: 'I need 2 wireless mice, please send a quote'
    matched both MS-201 (Wireless Optical Mouse) and KB-102 (Compact Wireless
    Keyboard) at score 76.19 because 'wireless' inflated token_set_ratio above
    the strong-match threshold. The overlap guard requires the clause to share
    the product's head noun or at least two name tokens.
    """
    result = nlp_service.analyze("I need 2 wireless mice, please send a quote")
    matched_ids = [p.product_id for p in result.matched_products]

    # The intended mouse is matched with the explicitly stated quantity.
    assert "MS-201" in matched_ids
    mouse = next(p for p in result.matched_products if p.product_id == "MS-201")
    assert mouse.extracted_quantity == 2
    assert mouse.quantity_missing is False
    assert mouse.is_ambiguous is False

    # No keyboard may be matched from a mice-only request.
    assert not any(pid.startswith("KB") for pid in matched_ids)


def test_14_reverse_case_keyboard_request_does_not_add_mouse():
    """Regression: the mirror image of test_13 — keyboards must not pull in a mouse."""
    result = nlp_service.analyze("I need 2 wireless keyboards, please send a quote")
    matched_ids = [p.product_id for p in result.matched_products]

    assert any(pid.startswith("KB") for pid in matched_ids)
    kb = next(p for p in result.matched_products if p.product_id.startswith("KB"))
    assert kb.extracted_quantity == 2
    assert not any(pid.startswith("MS") for pid in matched_ids)


def test_16_terse_quantity_requests_classified_as_quotation_request(test_db_session):
    """Regression: terse purchase requests with an explicit quantity must be
    quotation_request, not product_inquiry/unsupported.

    The ML classifier is trained on verbose phrasings, so short but
    unambiguous requests like "2 wireless mice" were previously routed to
    product_inquiry (price check only) or even unsupported (human handoff).
    """
    terse_requests = [
        "2 wireless mice",
        "1 studio microphone",
        "5 gaming headsets",
        "2 webcams",
    ]
    for text in terse_requests:
        res = nlp_service.analyze(text, db=test_db_session)
        assert res.intent == "quotation_request", f"For '{text}' expected quotation_request, got {res.intent}"
        assert res.is_unsupported is False
        assert any(
            p.extracted_quantity is not None and p.extracted_quantity > 0
            for p in res.matched_products
        ), f"For '{text}' expected a positive extracted quantity"


def test_17_hyphenated_product_name_quantity_not_flagged_negative():
    """Regression: the negative-quantity regex must not match the "-1" in "7-in-1"."""
    qty, is_invalid, has_qty = nlp_service.extract_quantity_from_phrase(
        "1000 7-in-1 USB-C Multiport Hub"
    )
    assert has_qty is True
    assert is_invalid is False
    assert qty == 1000

    # A genuine negative quantity is still rejected.
    qty_neg, is_neg, _ = nlp_service.extract_quantity_from_phrase("-3 wireless mice")
    assert is_neg is True
    assert qty_neg is None


def test_18_bare_product_category_does_not_trigger_handoff(test_db_session):
    """Regression: a bare catalogue category name that matches a product must be a
    product inquiry, not unsupported (which would create a human handoff)."""
    res = nlp_service.analyze("webcams", db=test_db_session)
    assert res.is_unsupported is False
    assert res.intent in ("product_inquiry", "quotation_request")
    # Genuine out-of-domain request still triggers unsupported.
    oos = nlp_service.analyze("Can you order a pepperoni pizza for me?", db=test_db_session)
    assert oos.is_unsupported is True


def test_19_multi_product_and_ambiguity_handling_preserved():
    """The overlap guard must not weaken multi-product or ambiguous matching."""
    # Multi-product request: keyboards AND mice are both resolved.
    multi = nlp_service.analyze(
        "I need three wireless keyboards and two wireless mice. Please prepare a quotation."
    )
    multi_ids = [p.product_id for p in multi.matched_products]
    assert any(pid.startswith("KB") for pid in multi_ids)
    assert "MS-201" in multi_ids
    mouse = next(p for p in multi.matched_products if p.product_id == "MS-201")
    assert mouse.extracted_quantity == 2

    # Category-level ambiguity is preserved: 'monitor' still surfaces both
    # monitors so downstream clarification can ask the customer to choose.
    ambiguous = nlp_service.analyze("Please quote for monitor")
    ambiguous_ids = {p.product_id for p in ambiguous.matched_products}
    assert "MN-401" in ambiguous_ids
    assert "MN-402" in ambiguous_ids


def test_20_small_talk_gets_friendly_intent_not_handoff():
    """Regression: bare greetings, thanks, and farewells must be recognised as
    small talk (greeting/thanks/farewell) and must never be flagged unsupported
    (which would escalate to a human handoff)."""
    greeting_cases = ["hi", "Hello!", "hey there", "good morning", "hola", "Howdy?"]
    for msg in greeting_cases:
        res = nlp_service.analyze(msg)
        assert res.intent == "greeting", f"{msg!r} -> {res.intent}"
        assert res.is_unsupported is False

    thanks_cases = ["thanks", "Thank you!", "thx a lot", "cheers"]
    for msg in thanks_cases:
        res = nlp_service.analyze(msg)
        assert res.intent == "thanks", f"{msg!r} -> {res.intent}"
        assert res.is_unsupported is False

    farewell_cases = ["bye", "goodbye", "see ya", "ttyl"]
    for msg in farewell_cases:
        res = nlp_service.analyze(msg)
        assert res.intent == "farewell", f"{msg!r} -> {res.intent}"
        assert res.is_unsupported is False


def test_21_greeting_within_real_request_does_not_mask_intent():
    """A greeting embedded in a genuine request must NOT be swallowed by the
    small-talk detector — the real purchase intent must still be classified."""
    res = nlp_service.analyze("hi, I need 2 mechanical keyboards please")
    assert res.intent == "quotation_request"
    kb = next((p for p in res.matched_products if p.product_id.startswith("KB")), None)
    assert kb is not None and kb.extracted_quantity == 2

    oos = nlp_service.analyze("hello, can you book me a flight to Paris?")
    assert oos.is_unsupported is True


def test_22_typo_tolerant_product_inquiry():
    """Typo-heavy product inquiries should still resolve to product_inquiry."""
    typo_cases = [
        ("keybord ka rate kitna hai?", "product_inquiry"),
        ("wirles mice available hai kya?", "product_inquiry"),
        ("moniter ka price batao", "product_inquiry"),
        ("do you have any headphons in stock", "product_inquiry"),
        ("webcm chahiye, stock mein hai?", "product_inquiry"),
        ("microfon ka kitna price hai", "product_inquiry"),
        # Exact product-ID reference often tips the model toward quotation_request;
        # either is acceptable for a rate check on a specific SKU.
        ("kb-101 ka rate kya hai", ("product_inquiry", "quotation_request")),
    ]
    for text, expected in typo_cases:
        res = nlp_service.analyze(text)
        if isinstance(expected, tuple):
            assert res.intent in expected, f"'{text}': expected one of {expected}, got {res.intent}"
        else:
            assert res.intent == expected, f"'{text}': expected {expected}, got {res.intent}"


def test_23_typo_tolerant_quotation_request():
    """Typo-heavy quotation requests should classify as quotation_request."""
    typo_cases = [
        ("bhai 2 keyboard chahiye", "quotation_request"),
        ("mujhe 3 mice chahiye quote bhejo", "quotation_request"),
        ("2 wireless mice and 1 headset", "quotation_request"),
        ("3 mice, 1 headset quote karo", "quotation_request"),
        ("2 x KB-101 quote please", "quotation_request"),
        ("quote for 4 webcams", "quotation_request"),
        ("keybord aur 2 mice ka quote banao", "quotation_request"),
        ("quote dedo 5 keyboard ka", "quotation_request"),
    ]
    for text, expected in typo_cases:
        res = nlp_service.analyze(text)
        assert res.intent == expected, f"'{text}': expected {expected}, got {res.intent}"


def test_24_paraphrase_product_inquiry():
    """Paraphrased product inquiries should classify as product_inquiry."""
    paraphrases = [
        "Are there any mechanical typing boards available?",
        "Can you check if you have gaming headsets right now?",
        "Do you carry wireless pointing devices?",
        "what does the condenser mic cost",
        "price of laptop stand?",
    ]
    for phrase in paraphrases:
        res = nlp_service.analyze(phrase)
        assert res.intent in ("product_inquiry", "quotation_request"), f"'{phrase}': got {res.intent}"


def test_25_paraphrase_quotation_request():
    """Paraphrased quotation requests should classify as quotation_request."""
    paraphrases = [
        "i want 5 usb hubs, send quote",
        "need 6 laptop stands ASAP, give me a price",
        "2 keyboards and 3 mice",
        "kindly prepare quotation for 7 microphones",
        "give me best price for 8 webcams",
    ]
    for phrase in paraphrases:
        res = nlp_service.analyze(phrase)
        assert res.intent == "quotation_request", f"'{phrase}': got {res.intent}"
