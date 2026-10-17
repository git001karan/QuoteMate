"""Automated test suite for Milestone 6: Quotation calculation, stock, and confirmation."""

from decimal import Decimal
import sqlite3

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ProductModel, QuotationItemModel, QuotationModel
from app.schemas import IncomingMessage
from app.services.cart_service import cart_service
from app.services.catalogue_service import catalogue_service
from app.services.conversation_service import ConversationState, conversation_service
from app.services.message_service import message_service
from app.services.quotation_service import (
    QuotationStatus,
    configured_tax_rate,
    money,
    quotation_service,
)


@pytest.fixture
def isolated_db(tmp_path):
    """Create an isolated test SQLite engine and session factory with a seeded catalogue."""
    db_file = tmp_path / "test_m6.db"
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

    init_session = TestingSession()
    catalogue_service.seed_catalogue_if_empty(db=init_session)
    init_session.close()

    yield engine, TestingSession
    engine.dispose()


def _add_to_cart(session, sender_id: str, items: list[tuple[str, int]]) -> None:
    for product_id, quantity in items:
        cart_service.upsert_item(sender_id, product_id, quantity, mode="set", db=session)


def test_1_line_totals_and_subtotal_for_multiple_products(isolated_db):
    """Requirement 1: Line totals equal unit price × quantity and subtotal sums all lines."""
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "quote_multi_line"

    _add_to_cart(session, sender, [("KB-101", 2), ("MS-201", 3)])
    breakdown = quotation_service.evaluate_items(
        sender, [("KB-101", 2), ("MS-201", 3)], session, persist_draft=False
    )

    kb = next(i for i in breakdown.items if i.product_id == "KB-101")
    ms = next(i for i in breakdown.items if i.product_id == "MS-201")
    assert kb.unit_price == Decimal("3499.00")
    assert kb.quantity == 2
    assert kb.line_total == Decimal("6998.00")
    assert ms.unit_price == Decimal("799.00")
    assert ms.quantity == 3
    assert ms.line_total == Decimal("2397.00")
    assert breakdown.subtotal == Decimal("9395.00")
    assert breakdown.subtotal == kb.line_total + ms.line_total
    assert breakdown.enquiry_id is None
    session.close()


def test_2_configured_tax_and_final_total(isolated_db):
    """Requirement 2: Tax uses the configured rate and total is subtotal + tax."""
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "quote_tax"

    breakdown = quotation_service.evaluate_items(
        sender, [("KB-101", 2), ("MS-201", 2)], session, persist_draft=False
    )
    tax_rate = configured_tax_rate()
    expected_subtotal = Decimal("6998.00") + Decimal("1598.00")
    expected_tax = money(expected_subtotal * tax_rate)
    expected_total = money(expected_subtotal + expected_tax)

    assert breakdown.tax_rate == tax_rate
    assert breakdown.subtotal == expected_subtotal
    assert breakdown.tax_amount == expected_tax
    assert breakdown.total == expected_total
    assert breakdown.total == breakdown.subtotal + breakdown.tax_amount
    session.close()


def test_3_monetary_rounding_and_decimal_precision(isolated_db):
    """Requirement 3: Totals use Decimal half-up rounding to two places, not float."""
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "quote_rounding"

    product = session.get(ProductModel, "LP-801")
    product.price = Decimal("100.25")
    session.flush()

    breakdown = quotation_service.evaluate_items(
        sender, [("LP-801", 1)], session, persist_draft=False
    )
    # 100.25 * 0.18 = 18.045 -> 18.05 with ROUND_HALF_UP
    assert breakdown.subtotal == Decimal("100.25")
    assert breakdown.tax_amount == Decimal("18.05")
    assert breakdown.total == Decimal("118.30")
    assert isinstance(breakdown.subtotal, Decimal)
    assert isinstance(breakdown.tax_amount, Decimal)
    assert isinstance(breakdown.total, Decimal)
    session.close()


def test_4_unknown_or_unavailable_products(isolated_db):
    """Requirement 4: Unknown and zero-stock products block the quotation without an enquiry."""
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "quote_unknown"

    unknown = quotation_service.evaluate_items(
        sender, [("ZZ-999", 1)], session, persist_draft=True
    )
    assert unknown.is_valid is False
    assert unknown.enquiry_id is None
    assert unknown.quotation_id is None
    assert unknown.stock_issues[0].reason == "unknown"
    assert unknown.stock_issues[0].requested_quantity == 1
    assert unknown.stock_issues[0].available_quantity == 0

    webcam = session.get(ProductModel, "WC-501")
    webcam.stock = 0
    session.flush()
    unavailable = quotation_service.evaluate_items(
        sender, [("WC-501", 2)], session, persist_draft=True
    )
    assert unavailable.is_valid is False
    assert unavailable.enquiry_id is None
    assert unavailable.stock_issues[0].reason == "unavailable"
    assert unavailable.stock_issues[0].available_quantity == 0
    assert unavailable.stock_issues[0].requested_quantity == 2
    assert session.scalar(select(QuotationModel).where(QuotationModel.sender_id == sender)) is None
    session.close()


def test_5_insufficient_stock(isolated_db):
    """Requirement 5: Requested quantity above available stock is explained and not confirmed."""
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "quote_low_stock"

    kb = session.get(ProductModel, "KB-101")
    kb.stock = 2
    session.flush()

    _add_to_cart(session, sender, [("KB-101", 5)])
    breakdown = quotation_service.prepare_draft(sender, db=session)

    assert breakdown.is_valid is False
    assert breakdown.enquiry_id is None
    issue = breakdown.stock_issues[0]
    assert issue.reason == "insufficient_stock"
    assert issue.requested_quantity == 5
    assert issue.available_quantity == 2
    assert "insufficient stock" in issue.reason or issue.available_quantity == 2
    # Cart is left unchanged; items are not silently removed.
    cart = cart_service.get_cart(sender, db=session)
    assert cart.items[0].quantity == 5
    session.close()


def test_6_no_enquiry_id_before_customer_confirmation(isolated_db):
    """Requirement 6: Draft quotations do not receive an enquiry ID."""
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "quote_draft_only"

    msg = IncomingMessage(
        message_id="M6-DRAFT-1",
        sender_id=sender,
        text="Please quote for two mechanical keyboards",
    )
    reply = message_service.process_incoming_message(msg, db=session)

    assert reply.conversation_state == ConversationState.AWAITING_CONFIRMATION
    assert reply.enquiry_id is None
    assert reply.quotation_id is not None
    assert reply.quotation_status == QuotationStatus.DRAFT
    assert "Draft Quotation" in reply.reply_text
    assert "Please reply yes to confirm" in reply.reply_text

    stored = session.scalar(
        select(QuotationModel).where(QuotationModel.quotation_id == reply.quotation_id)
    )
    assert stored.status == QuotationStatus.DRAFT
    assert stored.enquiry_id is None
    session.close()


def test_7_successful_confirmation_creates_exactly_one_enquiry_id(isolated_db):
    """Requirement 7: Confirming a valid draft creates exactly one enquiry ID."""
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "quote_confirm_one"

    message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-CONF-1",
            sender_id=sender,
            text="Please quote for two mechanical keyboards",
        ),
        db=session,
    )
    reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-CONF-2",
            sender_id=sender,
            text="Yes, please confirm this quotation.",
        ),
        db=session,
    )

    assert reply.conversation_state == ConversationState.CONFIRMED
    assert reply.enquiry_id is not None
    assert reply.enquiry_id.startswith("ENQ-")
    assert "confirmed" in reply.reply_text.lower()

    rows = session.scalars(
        select(QuotationModel).where(
            QuotationModel.sender_id == sender,
            QuotationModel.status == QuotationStatus.CONFIRMED,
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].enquiry_id == reply.enquiry_id

    enquiry_ids = session.scalars(
        select(QuotationModel.enquiry_id).where(QuotationModel.sender_id == sender)
    ).all()
    assert enquiry_ids.count(reply.enquiry_id) == 1
    session.close()


def test_8_decline_does_not_create_confirmed_enquiry(isolated_db):
    """Requirement 8: Declining a draft cancels it without creating an enquiry ID."""
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "quote_decline"

    draft_reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-DEC-1",
            sender_id=sender,
            text="Please quote for two mechanical keyboards",
        ),
        db=session,
    )
    decline_reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-DEC-2",
            sender_id=sender,
            text="No, cancel this quotation.",
        ),
        db=session,
    )

    assert decline_reply.conversation_state == ConversationState.DECLINED
    assert decline_reply.enquiry_id is None
    stored = session.scalar(
        select(QuotationModel).where(QuotationModel.quotation_id == draft_reply.quotation_id)
    )
    assert stored.status == QuotationStatus.CANCELLED
    assert stored.enquiry_id is None
    confirmed = session.scalars(
        select(QuotationModel).where(
            QuotationModel.sender_id == sender,
            QuotationModel.status == QuotationStatus.CONFIRMED,
        )
    ).all()
    assert confirmed == []
    session.close()


def test_9_repeated_confirmation_does_not_create_duplicate_enquiries(isolated_db):
    """Requirement 9: A second confirmation message reuses the original enquiry ID."""
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "quote_dup_confirm"

    message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-DUP-1",
            sender_id=sender,
            text="Please quote for two mechanical keyboards",
        ),
        db=session,
    )
    first = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-DUP-2",
            sender_id=sender,
            text="Yes, please confirm this quotation.",
        ),
        db=session,
    )
    second = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-DUP-3",
            sender_id=sender,
            text="Yes, please confirm this quotation.",
        ),
        db=session,
    )

    assert first.enquiry_id is not None
    assert second.enquiry_id == first.enquiry_id
    confirmed = session.scalars(
        select(QuotationModel).where(
            QuotationModel.sender_id == sender,
            QuotationModel.status == QuotationStatus.CONFIRMED,
        )
    ).all()
    assert len(confirmed) == 1
    assert confirmed[0].enquiry_id == first.enquiry_id
    session.close()


def test_10_cart_changes_recalculate_the_draft(isolated_db):
    """Requirement 10: Changing cart quantities recalculates the pending draft totals."""
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "quote_recalc"

    first = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-RE-1",
            sender_id=sender,
            text="Please quote for two mechanical keyboards",
        ),
        db=session,
    )
    original_total = first.quotation.total
    original_qty = first.quotation.items[0].quantity
    assert original_qty == 2

    second = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-RE-2",
            sender_id=sender,
            text="Could you calculate a quote for five mechanical keyboards?",
        ),
        db=session,
    )

    assert second.quotation_status == QuotationStatus.DRAFT
    assert second.enquiry_id is None
    assert second.quotation.items[0].quantity == 5
    assert second.quotation.total != original_total
    assert second.quotation.subtotal == Decimal("17495.00")
    session.close()


def test_11_stock_or_price_changes_before_confirmation_are_handled_safely(isolated_db):
    """Requirement 11: Confirmation re-reads current stock and prices; draft does not decrement stock."""
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "quote_stale"

    message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-STALE-1",
            sender_id=sender,
            text="Please quote for two mechanical keyboards",
        ),
        db=session,
    )
    kb = session.get(ProductModel, "KB-101")
    stock_after_draft = kb.stock
    assert stock_after_draft == 25

    kb.price = Decimal("4000.00")
    session.flush()

    confirmed = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-STALE-2",
            sender_id=sender,
            text="Yes, please confirm this quotation.",
        ),
        db=session,
    )
    assert confirmed.enquiry_id is not None
    assert confirmed.quotation.items[0].unit_price == Decimal("4000.00")
    assert confirmed.quotation.subtotal == Decimal("8000.00")
    kb_after = session.get(ProductModel, "KB-101")
    assert kb_after.stock == 23

    # Historical snapshot is kept after a later catalogue price change.
    kb_after.price = Decimal("100.00")
    session.flush()
    stored = session.scalar(
        select(QuotationModel).where(QuotationModel.quotation_id == confirmed.quotation_id)
    )
    assert stored.items[0].unit_price == Decimal("4000.00")
    assert stored.total == confirmed.quotation.total

    sender_b = "quote_stale_stock"
    message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-STALE-3",
            sender_id=sender_b,
            text="Please quote for two wireless mice",
        ),
        db=session,
    )
    mouse = session.get(ProductModel, "MS-201")
    mouse.stock = 1
    session.flush()
    failed = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-STALE-4",
            sender_id=sender_b,
            text="Yes, please confirm this quotation.",
        ),
        db=session,
    )
    assert failed.enquiry_id is None
    assert failed.conversation_state != ConversationState.CONFIRMED
    assert any(issue.reason == "insufficient_stock" for issue in failed.quotation.stock_issues)
    session.close()


def test_12_customers_cannot_access_or_confirm_each_others_quotations(isolated_db):
    """Requirement 12: Quotations are isolated by sender_id."""
    _, TestingSession = isolated_db
    session = TestingSession()
    alice = "quote_alice"
    bob = "quote_bob"

    alice_reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-ISO-A1",
            sender_id=alice,
            text="Please quote for two mechanical keyboards",
        ),
        db=session,
    )
    message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-ISO-B1",
            sender_id=bob,
            text="Please quote for one 4K UHD monitor",
        ),
        db=session,
    )

    assert quotation_service.get_for_sender(alice_reply.quotation_id, bob, db=session) is None
    assert (
        quotation_service.get_for_sender(alice_reply.quotation_id, alice, db=session) is not None
    )

    bob_confirm = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-ISO-B2",
            sender_id=bob,
            text="Yes, please confirm this quotation.",
        ),
        db=session,
    )
    alice_quotes = quotation_service.list_for_sender(alice, db=session)
    bob_quotes = quotation_service.list_for_sender(bob, db=session)
    assert all(q.sender_id == alice for q in alice_quotes)
    assert all(q.sender_id == bob for q in bob_quotes)
    assert alice_quotes[0].enquiry_id is None
    assert bob_confirm.enquiry_id is not None
    assert alice_quotes[0].enquiry_id != bob_confirm.enquiry_id
    session.close()


def test_13_draft_and_confirmed_quotations_persist_across_sessions(isolated_db):
    """Requirement 13: Draft and confirmed quotations survive session close / restart."""
    _, TestingSession = isolated_db
    sender = "quote_persist"

    s1 = TestingSession()
    draft_reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-PER-1",
            sender_id=sender,
            text="Please quote for two mechanical keyboards",
        ),
        db=s1,
    )
    s1.commit()
    quotation_id = draft_reply.quotation_id
    s1.close()

    s2 = TestingSession()
    restored = s2.scalar(
        select(QuotationModel).where(QuotationModel.quotation_id == quotation_id)
    )
    assert restored is not None
    assert restored.status == QuotationStatus.DRAFT
    assert restored.enquiry_id is None
    items = s2.scalars(
        select(QuotationItemModel).where(QuotationItemModel.quotation_id == quotation_id)
    ).all()
    assert len(items) == 1
    assert items[0].unit_price == Decimal("3499.00")

    confirm_reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-PER-2",
            sender_id=sender,
            text="Yes, please confirm this quotation.",
        ),
        db=s2,
    )
    s2.commit()
    enquiry_id = confirm_reply.enquiry_id
    s2.close()

    s3 = TestingSession()
    confirmed = s3.scalar(
        select(QuotationModel).where(QuotationModel.quotation_id == quotation_id)
    )
    assert confirmed.status == QuotationStatus.CONFIRMED
    assert confirmed.enquiry_id == enquiry_id
    conv = conversation_service.get_by_sender(sender, db=s3)
    assert conv.state == ConversationState.CONFIRMED
    s3.close()


def test_14_unrelated_message_is_not_treated_as_confirmation(isolated_db):
    """Confirmation must be explicit; an unrelated message must not create an enquiry."""
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "quote_unrelated"

    message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-UN-1",
            sender_id=sender,
            text="Please quote for two mechanical keyboards",
        ),
        db=session,
    )
    reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M6-UN-2",
            sender_id=sender,
            text="What are your business operating hours?",
        ),
        db=session,
    )

    assert reply.enquiry_id is None
    confirmed = session.scalars(
        select(QuotationModel).where(
            QuotationModel.sender_id == sender,
            QuotationModel.status == QuotationStatus.CONFIRMED,
        )
    ).all()
    assert confirmed == []
    session.close()
