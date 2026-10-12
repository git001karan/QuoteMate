"""Database configuration and session management for QuoteMate using SQLAlchemy."""

import sqlite3
from typing import Generator
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL

# Connect arguments: check_same_thread=False allows FastAPI threads to share SQLite connections safely
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)


# Enforce SQLite foreign key constraints (SQLite has foreign keys disabled by default)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key constraints for SQLite connections."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Session factory bound to the engine
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base class for all database models."""

    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped database session with guaranteed closure.

    Yields:
        Session: Active SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(custom_engine: Engine | None = None) -> None:
    """Initialize database tables using SQLAlchemy metadata.

    Note:
        Base.metadata.create_all is idempotent and non-destructive: it creates
        tables only if they do not already exist. It does NOT drop existing tables
        or alter existing columns. Future production schema changes should use
        Alembic database migrations.
    """
    target_engine = custom_engine or engine
    Base.metadata.create_all(bind=target_engine)
