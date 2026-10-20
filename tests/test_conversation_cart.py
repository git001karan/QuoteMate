"""Automated test suite for Milestone 5: Conversation State and Cart Management."""

from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
import sqlite3

from app.database import Base, get_db
from app.main import app
from app.schemas import IncomingMessage
from app.services.cart_service import cart_service
from app.services.catalogue_service import catalogue_service
from app.services.conversation_service import ConversationState, conversation_service
from app.services.message_service import message_service


@pytest.fixture
def isolated_db(tmp_path):
    """Create an isolated test SQLite engine and session factory with pre-seeded catalogue."""
    db_file = tmp_path / "test_m5.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed products into isolated database
    init_session = TestingSession()
    catalogue_service.seed_catalogue_if_empty(db=init_session)
    init_session.close()

    yield engine, TestingSession
    engine.dispose()


@pytest.fixture
def client_with_db(isolated_db):
    """Provide a FastAPI TestClient configured to use the isolated database."""
    engine, TestingSession = isolated_db

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client, TestingSession
    app.dependency_overrides.clear()


# =============================================================================
# 1. Separate Customers & Cart Isolation
# =============================================================================

def test_1_separate_customers_have_independent_conversations_and_carts(isolated_db):
    """Requirement 1 & 10: Two distinct senders have isolated conversation states and carts."""
    _, TestingSession = isolated_db
    session = TestingSession()

    user_a = "customer_alice_001"
    user_b = "customer_bob_002"

    # Alice adds 2 keyboards
    msg_a = IncomingMessage(
        message_id="MSG-A-1",
        sender_id=user_a,
        text="I need two mechanical keyboards, please quote",
    )
    reply_a = message_service.process_incoming_message(msg_a, db=session)
    assert reply_a.duplicated is False

    # Bob adds 1 4K monitor
    msg_b = IncomingMessage(
        message_id="MSG-B-1",
        sender_id=user_b,
        text="I want to buy one 4K UHD monitor, send quote",
    )
    reply_b = message_service.process_incoming_message(msg_b, db=session)
    assert reply_b.duplicated is False

    # Check Alice's cart
    cart_a = cart_service.get_cart(user_a, db=session)
    assert len(cart_a.items) == 1
    assert cart_a.items[0].product_id == "KB-101"
    assert cart_a.items[0].quantity == 2

    # Check Bob's cart
    cart_b = cart_service.get_cart(user_b, db=session)
    assert len(cart_b.items) == 1
    assert cart_b.items[0].product_id == "MN-401"
    assert cart_b.items[0].quantity == 1

    # Verify Alice's cart has NO monitor, and Bob's cart has NO keyboard
    alice_pids = {i.product_id for i in cart_a.items}
    bob_pids = {i.product_id for i in cart_b.items}
    assert "MN-401" not in alice_pids
    assert "KB-101" not in bob_pids

    # Alice clears her cart
    cart_service.clear_cart(user_a, db=session)
    assert cart_service.get_cart(user_a, db=session).is_empty is True
    # Bob's cart must remain unaffected
    assert cart_service.get_cart(user_b, db=session).is_empty is False
    assert len(cart_service.get_cart(user_b, db=session).items) == 1

    session.close()


# =============================================================================
# 2. Missing Quantity Follow-up and Pending Product Memory
# =============================================================================

def test_2_missing_quantity_triggers_follow_up_and_remembers_product(isolated_db):
    """Requirement 4 & 5: When product is identified without quantity, ask and remember product."""
    _, TestingSession = isolated_db
    session = TestingSession()

    user = "customer_multi_turn_01"
    msg = IncomingMessage(
        message_id="MSG-MT-1",
        sender_id=user,
        text="Please prepare a quote for mechanical keyboards.",
    )
    reply = message_service.process_incoming_message(msg, db=session)

    # Check reply and state
    assert reply.needs_clarification is True
    assert "How many units" in reply.reply_text
    assert reply.conversation_state == ConversationState.AWAITING_QUANTITY

    # Verify conversation record in database remembers pending_product_id
    conv = conversation_service.get_by_sender(user, db=session)
    assert conv is not None
    assert conv.state == ConversationState.AWAITING_QUANTITY
    assert conv.pending_product_id == "KB-101"

    # Cart must still be empty
    cart = cart_service.get_cart(user, db=session)
    assert cart.is_empty is True

    session.close()


def test_3_follow_up_quantity_message_completes_pending_request(isolated_db):
    """Requirement 5: Customer's next message '2' completes the pending request."""
    _, TestingSession = isolated_db
    session = TestingSession()

    user = "customer_multi_turn_02"
    # Step 1: Enquire without quantity
    msg1 = IncomingMessage(
        message_id="MSG-MT-2A",
        sender_id=user,
        text="I want to get a quotation for mechanical keyboards.",
    )
    reply1 = message_service.process_incoming_message(msg1, db=session)
    assert reply1.conversation_state == ConversationState.AWAITING_QUANTITY

    # Step 2: Customer responds with digit "2"
    msg2 = IncomingMessage(
        message_id="MSG-MT-2B",
        sender_id=user,
        text="2",
    )
    reply2 = message_service.process_incoming_message(msg2, db=session)

    # Verify completion
    assert "Added 2 x Ergonomic Mechanical Keyboard" in reply2.reply_text
    assert reply2.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert reply2.cart is not None
    assert len(reply2.cart.items) == 1
    assert reply2.cart.items[0].product_id == "KB-101"
    assert reply2.cart.items[0].quantity == 2

    # Verify pending product is cleared in database
    conv = conversation_service.get_by_sender(user, db=session)
    assert conv.pending_product_id is None

    session.close()


def test_4_follow_up_with_written_number_word(isolated_db):
    """Requirement 5 & 6: Written number words ('three', 'five') complete pending requests."""
    _, TestingSession = isolated_db
    session = TestingSession()

    user = "customer_multi_turn_03"
    # Step 1: Missing quantity
    msg1 = IncomingMessage(
        message_id="MSG-WORD-1",
        sender_id=user,
        text="Quote me for USB-C multiport hubs",
    )
    message_service.process_incoming_message(msg1, db=session)

    # Step 2: Follow-up with word "three"
    msg2 = IncomingMessage(
        message_id="MSG-WORD-2",
        sender_id=user,
        text="three units please",
    )
    reply2 = message_service.process_incoming_message(msg2, db=session)

    assert "Added 3 x 7-in-1 USB-C Multiport Hub" in reply2.reply_text
    cart = cart_service.get_cart(user, db=session)
    assert len(cart.items) == 1
    assert cart.items[0].product_id == "HB-601"
    assert cart.items[0].quantity == 3

    session.close()


# =============================================================================
# 3. Invalid Quantities (Zero and Negative)
# =============================================================================

def test_5_zero_and_negative_quantities_rejected(isolated_db):
    """Requirement 7: Zero and negative quantities are rejected and never added to cart."""
    _, TestingSession = isolated_db
    session = TestingSession()

    user = "customer_invalid_qty"

    # Direct message with 0 quantity
    msg_zero = IncomingMessage(
        message_id="MSG-ZERO-1",
        sender_id=user,
        text="Quote for 0 wireless mice",
    )
    reply_zero = message_service.process_incoming_message(msg_zero, db=session)
    assert reply_zero.needs_clarification is True
    assert "positive number greater than 0" in reply_zero.reply_text
    assert cart_service.get_cart(user, db=session).is_empty is True

    # Multi-turn follow-up with negative quantity "-3"
    msg_init = IncomingMessage(
        message_id="MSG-NEG-1",
        sender_id=user,
        text="Please quote for laptop stands",
    )
    message_service.process_incoming_message(msg_init, db=session)

    msg_neg = IncomingMessage(
        message_id="MSG-NEG-2",
        sender_id=user,
        text="-3",
    )
    reply_neg = message_service.process_incoming_message(msg_neg, db=session)
    assert reply_neg.needs_clarification is True
    assert "positive number greater than 0" in reply_neg.reply_text
    # State should remain AWAITING_QUANTITY, pending product preserved
    conv = conversation_service.get_by_sender(user, db=session)
    assert conv.state == ConversationState.AWAITING_QUANTITY
    assert conv.pending_product_id == "LP-801"
    assert cart_service.get_cart(user, db=session).is_empty is True

    session.close()


# =============================================================================
# 4. Unknown & Ambiguous Products
# =============================================================================

def test_6_unknown_product_clarification(isolated_db):
    """Requirement 6: Requesting an unknown product asks for clarification without altering cart."""
    _, TestingSession = isolated_db
    session = TestingSession()

    user = "customer_unknown_01"
    msg = IncomingMessage(
        message_id="MSG-UNK-1",
        sender_id=user,
        text="Do you sell refrigerators and washing machines?",
    )
    reply = message_service.process_incoming_message(msg, db=session)

    assert reply.needs_clarification is True
    assert cart_service.get_cart(user, db=session).is_empty is True

    session.close()


def test_7_ambiguous_product_clarification(isolated_db):
    """Requirement 6: Ambiguous product reference triggers clarification listing candidates."""
    _, TestingSession = isolated_db
    session = TestingSession()

    user = "customer_ambig_01"
    msg = IncomingMessage(
        message_id="MSG-AMB-1",
        sender_id=user,
        text="Please quote for monitor",
    )
    reply = message_service.process_incoming_message(msg, db=session)

    assert reply.needs_clarification is True
    assert reply.conversation_state == ConversationState.AWAITING_PRODUCT
    assert cart_service.get_cart(user, db=session).is_empty is True

    session.close()


# =============================================================================
# 5. Multiple Products & Repeated Additions
# =============================================================================

def test_8_multiple_products_added_in_single_message(isolated_db):
    """Requirement 3 & 8: Multiple products and quantities added in a single turn."""
    _, TestingSession = isolated_db
    session = TestingSession()

    user = "customer_multi_item"
    msg = IncomingMessage(
        message_id="MSG-MULTI-1",
        sender_id=user,
        text="I need three wireless keyboards and two wireless mice. Please prepare a quotation.",
    )
    reply = message_service.process_incoming_message(msg, db=session)

    assert reply.conversation_state == ConversationState.AWAITING_CONFIRMATION
    cart = cart_service.get_cart(user, db=session)
    assert len(cart.items) == 2
    # Verify subtotal equals sum of line totals
    expected_subtotal = sum(i.line_total for i in cart.items)
    assert cart.subtotal == expected_subtotal
    assert cart.subtotal > Decimal("0.00")

    session.close()


def test_9_repeated_additions_update_item_quantity(isolated_db):
    """Requirement 8: Re-stating product with new quantity updates item predictably."""
    _, TestingSession = isolated_db
    session = TestingSession()

    user = "customer_repeat_add"

    # Turn 1: Add 2 mechanical keyboards
    msg1 = IncomingMessage(
        message_id="MSG-REP-1",
        sender_id=user,
        text="Please quote for two mechanical keyboards",
    )
    message_service.process_incoming_message(msg1, db=session)
    cart1 = cart_service.get_cart(user, db=session)
    assert cart1.items[0].quantity == 2

    # Turn 2: Re-state mechanical keyboards with 5
    msg2 = IncomingMessage(
        message_id="MSG-REP-2",
        sender_id=user,
        text="Could you calculate a quote for five mechanical keyboards?",
    )
    message_service.process_incoming_message(msg2, db=session)
    cart2 = cart_service.get_cart(user, db=session)
    assert len(cart2.items) == 1
    assert cart2.items[0].quantity == 5

    session.close()


# =============================================================================
# 6. Cart Commands: View, Remove, and Clear
# =============================================================================

def test_10_cart_view_remove_and_clear_commands(isolated_db):
    """Requirement 7 & 8: Support viewing cart, removing item, and clearing cart."""
    _, TestingSession = isolated_db
    session = TestingSession()

    user = "customer_cart_cmds"

    # Add items to cart
    msg_add = IncomingMessage(
        message_id="MSG-CMD-1",
        sender_id=user,
        text="Please quote for 2 mechanical keyboards and 1 webcam",
    )
    message_service.process_incoming_message(msg_add, db=session)
    assert len(cart_service.get_cart(user, db=session).items) == 2

    # View cart command
    msg_view = IncomingMessage(
        message_id="MSG-CMD-2",
        sender_id=user,
        text="view cart",
    )
    reply_view = message_service.process_incoming_message(msg_view, db=session)
    assert "Current Cart:" in reply_view.reply_text
    assert "Ergonomic Mechanical Keyboard x 2" in reply_view.reply_text

    # Remove single item
    msg_rem = IncomingMessage(
        message_id="MSG-CMD-3",
        sender_id=user,
        text="remove mechanical keyboard",
    )
    reply_rem = message_service.process_incoming_message(msg_rem, db=session)
    assert "Removed Ergonomic Mechanical Keyboard from your cart" in reply_rem.reply_text
    cart_after_rem = cart_service.get_cart(user, db=session)
    assert len(cart_after_rem.items) == 1
    assert cart_after_rem.items[0].product_id == "WC-501"

    # Clear entire cart
    msg_clear = IncomingMessage(
        message_id="MSG-CMD-4",
        sender_id=user,
        text="clear cart",
    )
    reply_clear = message_service.process_incoming_message(msg_clear, db=session)
    assert "Your cart has been cleared." in reply_clear.reply_text
    assert cart_service.get_cart(user, db=session).is_empty is True

    session.close()


# =============================================================================
# 7. Confirmation & Decline Intents
# =============================================================================

def test_11_confirmation_and_decline_intents(isolated_db):
    """Requirement 9: Handle confirmation and decline intents without creating quotations."""
    _, TestingSession = isolated_db
    session = TestingSession()

    user = "customer_confirm_decline"

    # Add item
    msg_add = IncomingMessage(
        message_id="MSG-CD-1",
        sender_id=user,
        text="Please quote for two mechanical keyboards",
    )
    message_service.process_incoming_message(msg_add, db=session)

    # Customer confirms
    msg_conf = IncomingMessage(
        message_id="MSG-CD-2",
        sender_id=user,
        text="Yes, please confirm this quotation.",
    )
    reply_conf = message_service.process_incoming_message(msg_conf, db=session)
    assert reply_conf.conversation_state == ConversationState.CONFIRMED
    assert "confirmed" in reply_conf.reply_text.lower()

    # Customer later declines/cancels
    msg_dec = IncomingMessage(
        message_id="MSG-CD-3",
        sender_id=user,
        text="No, please cancel this quotation.",
    )
    reply_dec = message_service.process_incoming_message(msg_dec, db=session)
    assert reply_dec.conversation_state == ConversationState.DECLINED
    assert "cancelled" in reply_dec.reply_text.lower()

    session.close()


# =============================================================================
# 8. Duplicate Message ID Idempotency
# =============================================================================

def test_12_duplicate_message_id_rejected_and_idempotent(isolated_db):
    """Requirement 11: Replaying identical message_id does not apply cart modification twice."""
    _, TestingSession = isolated_db
    session = TestingSession()

    user = "customer_dup_test"
    msg = IncomingMessage(
        message_id="DUP-MSG-100",
        sender_id=user,
        text="Please quote for two mechanical keyboards",
    )

    # First send
    reply1 = message_service.process_incoming_message(msg, db=session)
    assert reply1.duplicated is False
    cart1 = cart_service.get_cart(user, db=session)
    assert cart1.items[0].quantity == 2

    # Second send with identical message_id
    reply2 = message_service.process_incoming_message(msg, db=session)
    assert reply2.duplicated is True
    assert reply2.reply_text == reply1.reply_text

    # Cart quantity must remain 2, not multiplied or modified
    cart2 = cart_service.get_cart(user, db=session)
    assert len(cart2.items) == 1
    assert cart2.items[0].quantity == 2

    session.close()


# =============================================================================
# 9. Persistence Across Database Restarts
# =============================================================================

def test_13_state_and_cart_persistence_across_sessions(isolated_db):
    """Requirement 2: Verify conversation state and cart persist across session restarts."""
    engine, TestingSession = isolated_db

    user = "customer_persistence_test"

    # Session 1: Initiate enquiry with missing quantity
    s1 = TestingSession()
    msg1 = IncomingMessage(
        message_id="PERSIST-1",
        sender_id=user,
        text="Please quote for mechanical keyboards",
    )
    message_service.process_incoming_message(msg1, db=s1)
    s1.commit()
    s1.close()  # Simulate application shutdown / session closure

    # Session 2: Read back from SQLite after "restart"
    s2 = TestingSession()
    conv = conversation_service.get_by_sender(user, db=s2)
    assert conv is not None
    assert conv.state == ConversationState.AWAITING_QUANTITY
    assert conv.pending_product_id == "KB-101"

    # Complete the request in Session 2
    msg2 = IncomingMessage(
        message_id="PERSIST-2",
        sender_id=user,
        text="4",
    )
    message_service.process_incoming_message(msg2, db=s2)
    s2.commit()
    s2.close()

    # Session 3: Verify cart items persisted
    s3 = TestingSession()
    cart = cart_service.get_cart(user, db=s3)
    assert len(cart.items) == 1
    assert cart.items[0].product_id == "KB-101"
    assert cart.items[0].quantity == 4
    s3.close()


# =============================================================================
# 10. Webhook & REST Endpoints
# =============================================================================

def test_14_fastapi_webhook_and_cart_endpoints(client_with_db):
    """Requirement 10: Verify FastAPI /webhook, /messages, /cart, and /conversations endpoints."""
    client, _ = client_with_db
    sender = "api_customer_01"

    # POST to /webhook
    response = client.post(
        "/webhook",
        json={
            "message_id": "WEBHOOK-MSG-1",
            "sender_id": sender,
            "text": "I need two mechanical keyboards, please quote",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message_id"] == "WEBHOOK-MSG-1"
    assert data["duplicated"] is False
    assert data["cart"]["is_empty"] is False
    assert len(data["cart"]["items"]) == 1

    # GET /cart/{sender_id}
    cart_resp = client.get(f"/cart/{sender}")
    assert cart_resp.status_code == 200
    cart_data = cart_resp.json()
    assert cart_data["subtotal"] > 0
    assert cart_data["items"][0]["quantity"] == 2

    # GET /conversations/{sender_id}
    conv_resp = client.get(f"/conversations/{sender}")
    assert conv_resp.status_code == 200
    assert conv_resp.json()["sender_id"] == sender

    # GET /conversations
    all_convs_resp = client.get("/conversations")
    assert all_convs_resp.status_code == 200
    assert len(all_convs_resp.json()) >= 1

    # DELETE /cart/{sender_id}
    del_resp = client.delete(f"/cart/{sender}")
    assert del_resp.status_code == 200
    assert del_resp.json()["message"] == "Cart cleared successfully"

    # Check cart is now empty
    cart_empty_resp = client.get(f"/cart/{sender}")
    assert cart_empty_resp.json()["is_empty"] is True


# =============================================================================
# 11. Regression: Generic-Token Cross-Match (wireless mice must not add a keyboard)
# =============================================================================

def test_15_wireless_mice_request_does_not_add_keyboard_to_cart(isolated_db):
    """Regression for the 'wireless' false-positive match.

    Before the fix, 'I need 2 wireless mice, please send a quote' matched
    KB-102 (Compact Wireless Keyboard) alongside MS-201 because the shared
    word 'wireless' inflated the fuzzy score above the strong threshold.
    The cart must contain exactly the mouse, with quantity 2.
    """
    _, TestingSession = isolated_db
    session = TestingSession()

    user = "customer_wireless_mice_regression"
    msg = IncomingMessage(
        message_id="REG-MICE-1",
        sender_id=user,
        text="I need 2 wireless mice, please send a quote",
    )
    reply = message_service.process_incoming_message(msg, db=session)

    assert reply.duplicated is False
    cart = cart_service.get_cart(user, db=session)
    cart_ids = [i.product_id for i in cart.items]

    assert "MS-201" in cart_ids
    assert not any(pid.startswith("KB") for pid in cart_ids), (
        f"Generic word 'wireless' must not add a keyboard to the cart, got: {cart_ids}"
    )
    assert len(cart.items) == 1
    assert cart.items[0].quantity == 2

    session.close()


def test_16_related_multi_product_and_ambiguous_requests_still_work(isolated_db):
    """The regression fix must not break multi-product carts or ambiguous clarification."""
    _, TestingSession = isolated_db
    session = TestingSession()

    # Multi-product: keyboards and mice in one message -> both categories in cart.
    user_multi = "customer_multi_regression"
    message_service.process_incoming_message(
        IncomingMessage(
            message_id="REG-MULTI-1",
            sender_id=user_multi,
            text="I need three wireless keyboards and two wireless mice. Please prepare a quotation.",
        ),
        db=session,
    )
    cart_multi = cart_service.get_cart(user_multi, db=session)
    multi_ids = {i.product_id for i in cart_multi.items}
    assert any(pid.startswith("KB") for pid in multi_ids)
    assert "MS-201" in multi_ids
    assert not any(pid.startswith("MN") or pid.startswith("HP") for pid in multi_ids)

    # Ambiguous category word: 'monitor' must ask for clarification, not pick one.
    user_amb = "customer_ambiguous_regression"
    reply_amb = message_service.process_incoming_message(
        IncomingMessage(
            message_id="REG-AMB-1",
            sender_id=user_amb,
            text="Please quote for monitor",
        ),
        db=session,
    )
    assert reply_amb.needs_clarification is True
    assert cart_service.get_cart(user_amb, db=session).is_empty is True

    session.close()
