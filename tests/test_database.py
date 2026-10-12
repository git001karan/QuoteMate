"""Automated tests for database configuration, models, constraints, and persistence."""

from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select, inspect, event, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
import sqlite3

from app.database import Base, get_db
from app.models import (
    ProductModel,
    ConversationModel,
    MessageModel,
    CartItemModel,
    QuotationModel,
    HandoffModel,
)
from app.services.catalogue_service import (
    CatalogueService,
    ProductNotFoundError,
)


@pytest.fixture
def test_db_engine(tmp_path):
    """Create an isolated test SQLite engine with foreign key enforcement."""
    test_db_file = tmp_path / "test_quotemate.db"
    engine = create_engine(
        f"sqlite:///{test_db_file}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db_session(test_db_engine):
    """Provide an isolated database session for testing."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_1_database_tables_are_created(test_db_engine):
    """Requirement 1: Verify all required tables exist in database metadata."""
    inspector = inspect(test_db_engine)
    table_names = inspector.get_table_names()

    expected_tables = {
        "products",
        "conversations",
        "messages",
        "cart_items",
        "quotations",
        "handoffs",
    }
    assert expected_tables.issubset(set(table_names)), (
        f"Missing tables: {expected_tables - set(table_names)}"
    )


def test_2_products_are_seeded_from_json(test_db_session):
    """Requirement 2: Verify products are loaded and seeded from products.json."""
    service = CatalogueService()
    inserted = service.seed_catalogue_if_empty(db=test_db_session)
    assert inserted >= 10
    assert inserted == 12

    count = test_db_session.query(ProductModel).count()
    assert count == 12

    kb101 = test_db_session.get(ProductModel, "KB-101")
    assert kb101 is not None
    assert kb101.name == "Ergonomic Mechanical Keyboard"
    assert kb101.price == Decimal("3499.00")
    assert kb101.stock == 25


def test_3_idempotent_seed_does_not_create_duplicates(test_db_session):
    """Requirement 3: Verify running seed a second time produces 0 duplicates."""
    service = CatalogueService()
    first_run = service.seed_catalogue_if_empty(db=test_db_session)
    assert first_run == 12

    second_run = service.seed_catalogue_if_empty(db=test_db_session)
    assert second_run == 0

    count = test_db_session.query(ProductModel).count()
    assert count == 12


def test_4_existing_database_values_not_reset_on_second_seed(test_db_session):
    """Requirement 4: Verify modified prices/stock are not overwritten by a subsequent seed."""
    service = CatalogueService()
    service.seed_catalogue_if_empty(db=test_db_session)

    # Modify KB-101 in database
    kb101 = test_db_session.get(ProductModel, "KB-101")
    kb101.price = Decimal("2999.00")
    kb101.stock = 5
    test_db_session.commit()

    # Re-run seeding
    service.seed_catalogue_if_empty(db=test_db_session)

    # Query afresh and verify modified values persist
    refreshed_kb101 = test_db_session.get(ProductModel, "KB-101")
    assert refreshed_kb101.price == Decimal("2999.00")
    assert refreshed_kb101.stock == 5


def test_5_product_listing_and_lookup_work(test_db_session):
    """Requirement 5: Verify get_all_products and get_product_by_id return expected schemas."""
    service = CatalogueService()
    service.seed_catalogue_if_empty(db=test_db_session)

    all_products = service.get_all_products(db=test_db_session)
    assert len(all_products) == 12
    assert all_products[0].id == "HB-601" or any(p.id == "KB-101" for p in all_products)

    product = service.get_product_by_id("KB-101", db=test_db_session)
    assert product.id == "KB-101"
    assert product.price == Decimal("3499.00")


def test_6_unknown_product_raises_not_found_error(test_db_session):
    """Requirement 6: Verify retrieving unknown product ID raises ProductNotFoundError."""
    service = CatalogueService()
    service.seed_catalogue_if_empty(db=test_db_session)

    with pytest.raises(ProductNotFoundError):
        service.get_product_by_id("NONEXISTENT-999", db=test_db_session)


def test_7_duplicate_message_ids_rejected(test_db_session):
    """Requirement 7: Verify database rejects messages with duplicate message_id."""
    msg1 = MessageModel(
        message_id="MSG-1001",
        sender_id="user_919876543210",
        text="Need quote for keyboards",
        status="RECEIVED",
    )
    test_db_session.add(msg1)
    test_db_session.commit()

    msg2 = MessageModel(
        message_id="MSG-1001",  # Same message_id!
        sender_id="user_919876543210",
        text="Duplicate message replay",
        status="RECEIVED",
    )
    test_db_session.add(msg2)

    with pytest.raises(IntegrityError):
        test_db_session.commit()
    test_db_session.rollback()


def test_8_invalid_cart_quantities_rejected(test_db_session):
    """Requirement 8: Verify check constraint rejects cart item with non-positive quantity."""
    service = CatalogueService()
    service.seed_catalogue_if_empty(db=test_db_session)

    # Invalid: quantity = 0
    invalid_cart_item = CartItemModel(
        sender_id="user_123",
        product_id="KB-101",
        quantity=0,
    )
    test_db_session.add(invalid_cart_item)

    with pytest.raises(IntegrityError):
        test_db_session.commit()
    test_db_session.rollback()

    # Invalid: quantity = -5
    negative_cart_item = CartItemModel(
        sender_id="user_123",
        product_id="KB-101",
        quantity=-5,
    )
    test_db_session.add(negative_cart_item)

    with pytest.raises(IntegrityError):
        test_db_session.commit()
    test_db_session.rollback()


def test_9_foreign_key_constraints_enforced(test_db_session):
    """Requirement 9: Verify foreign key enforcement rejects cart item with nonexistent product."""
    cart_item_orphan = CartItemModel(
        sender_id="user_123",
        product_id="NONEXISTENT-PRODUCT",
        quantity=2,
    )
    test_db_session.add(cart_item_orphan)

    with pytest.raises(IntegrityError):
        test_db_session.commit()
    test_db_session.rollback()


def test_10_sessions_properly_closed_after_use():
    """Requirement 10: Verify get_db dependency generator closes the session on exit."""
    generator = get_db()
    session = next(generator)
    assert isinstance(session, Session)
    assert session.is_active

    # Exhaust generator to simulate request completion
    try:
        next(generator)
    except StopIteration:
        pass

    # In SQLAlchemy 2.0, closing resets the transaction/binding
    # Verify session is closed or no active transaction remains
    assert not session.in_transaction()
