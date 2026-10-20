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


def _migrate_messages_idempotency_key(conn, target_engine: Engine) -> None:
    """Migrate the messages table from a global message_id unique constraint to
    a composite (sender_id, message_id) unique constraint.

    Older schema versions declared ``message_id VARCHAR(100) NOT NULL UNIQUE``.
    That rejected a legitimately independent event when two senders happened to
    reuse the same provider-level message ID, and worse, the replay path keyed
    on message_id alone could return one sender's reply to another sender.
    SQLite cannot drop a column-level UNIQUE without a table rebuild, so the
    migration rebuilds ``messages`` while preserving all rows.
    """
    from sqlalchemy import text

    ddl = conn.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name='messages'")
    ).scalar()
    if not ddl:
        return
    normalized = " ".join(ddl.split()).lower()
    # Old style: UNIQUE declared inline on the message_id column.
    old_style = (
        "message_id varchar(100) not null unique" in normalized
        or "message_id varchar(100) unique not null" in normalized
    )
    if not old_style:
        return

    conn.execute(
        text(
            """
            CREATE TABLE messages_migrated (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id VARCHAR(100) NOT NULL,
                sender_id VARCHAR(100) NOT NULL,
                text TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                response_text TEXT,
                status VARCHAR(50) NOT NULL DEFAULT 'RECEIVED',
                CONSTRAINT uq_messages_sender_id_message_id UNIQUE (sender_id, message_id)
            )
            """
        )
    )
    conn.execute(
        text(
            "INSERT INTO messages_migrated "
            "(id, message_id, sender_id, text, timestamp, response_text, status) "
            "SELECT id, message_id, sender_id, text, timestamp, response_text, status "
            "FROM messages"
        )
    )
    conn.execute(text("DROP TABLE messages"))
    conn.execute(text("ALTER TABLE messages_migrated RENAME TO messages"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_messages_message_id ON messages (message_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_messages_sender_id ON messages (sender_id)"))
    conn.commit()


def init_db(custom_engine: Engine | None = None) -> None:
    """Initialize database tables using SQLAlchemy metadata.

    Note:
        Base.metadata.create_all is idempotent and non-destructive: it creates
        tables only if they do not already exist. It does NOT drop existing tables
        or alter existing columns. Future production schema changes should use
        Alembic database migrations.
    """
    from sqlalchemy import inspect, text

    target_engine = custom_engine or engine
    Base.metadata.create_all(bind=target_engine)

    # Safely migrate existing SQLite table if columns were added later
    with target_engine.connect() as conn:
        inspector = inspect(target_engine)
        if "conversations" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("conversations")]
            if "pending_product_id" not in columns:
                conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN pending_product_id VARCHAR(50)")
                )
                conn.commit()
            if "context" not in columns:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN context TEXT"))
                conn.commit()

        if "quotations" in inspector.get_table_names():
            q_columns = [c["name"] for c in inspector.get_columns("quotations")]
            if "tax_rate" not in q_columns:
                conn.execute(
                    text(
                        "ALTER TABLE quotations ADD COLUMN tax_rate NUMERIC(10, 4) "
                        "NOT NULL DEFAULT 0.18"
                    )
                )
                conn.commit()
            if "enquiry_id" not in q_columns:
                conn.execute(text("ALTER TABLE quotations ADD COLUMN enquiry_id VARCHAR(100)"))
                conn.commit()
            if "confirmed_at" not in q_columns:
                conn.execute(text("ALTER TABLE quotations ADD COLUMN confirmed_at DATETIME"))
                conn.commit()
            if "updated_at" not in q_columns:
                conn.execute(text("ALTER TABLE quotations ADD COLUMN updated_at DATETIME"))
                conn.commit()
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_quotations_enquiry_id "
                    "ON quotations(enquiry_id)"
                )
            )
            conn.commit()

        if "messages" in inspector.get_table_names():
            _migrate_messages_idempotency_key(conn, target_engine)

