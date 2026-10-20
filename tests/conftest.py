"""Pytest configuration and session fixtures for QuoteMate."""

import sqlite3
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base, init_db
from app.services.catalogue_service import catalogue_service


@pytest.fixture(autouse=True, scope="session")
def setup_test_database():
    """Ensure database tables and initial catalogue seed exist during automated test runs."""
    init_db()
    catalogue_service.seed_catalogue_if_empty()


@pytest.fixture
def test_db_engine(tmp_path):
    """Create an isolated test SQLite engine with foreign key enforcement."""
    test_db_file = tmp_path / "test_isolated.db"
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
    """Provide an isolated database session with pre-seeded catalogue."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_db_engine
    )
    session = TestingSessionLocal()
    catalogue_service.seed_catalogue_if_empty(db=session)
    try:
        yield session
    finally:
        session.close()
