"""Automated test suite for Milestone 7: Human Handoff."""

import sqlite3

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import HandoffModel, QuotationModel
from app.schemas import IncomingMessage
from app.services.catalogue_service import catalogue_service
from app.services.message_service import message_service


@pytest.fixture
def isolated_db(tmp_path):
    db_file = tmp_path / "test_m7.db"
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


def test_unsupported_intent_creates_persisted_handoff(isolated_db):
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "handoff_unsupported"

    reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M7-HANDOFF-1",
            sender_id=sender,
            text="Can you order a pepperoni pizza for me?",
        ),
        db=session,
    )

    assert reply.is_unsupported is True
    assert reply.handoff_id is not None
    assert reply.handoff_status == "PENDING"

    handoff = session.scalar(
        select(HandoffModel).where(HandoffModel.id == reply.handoff_id)
    )
    assert handoff is not None
    assert handoff.sender_id == sender
    assert handoff.status == "PENDING"
    assert "pizza" in handoff.context.lower()
    assert handoff.created_at is not None
    session.close()


def test_handoff_contains_correct_conversation_context(isolated_db):
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "handoff_context"

    reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M7-CTX-1",
            sender_id=sender,
            text="Tell me a funny joke about programming.",
        ),
        db=session,
    )

    assert reply.handoff_id is not None
    handoff = session.scalar(
        select(HandoffModel).where(HandoffModel.id == reply.handoff_id)
    )
    assert handoff is not None
    assert "joke" in handoff.context.lower()
    assert "IDLE" in handoff.context or "AWAITING" in handoff.context
    assert handoff.reason is not None and len(handoff.reason) > 0
    session.close()


def test_customer_receives_simulated_handoff_response(isolated_db):
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "handoff_response"

    reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M7-RESP-1",
            sender_id=sender,
            text="What is the weather forecast in Bangalore tomorrow?",
        ),
        db=session,
    )

    assert reply.is_unsupported is True
    assert reply.handoff_id is not None
    assert "human" in reply.reply_text.lower() or "team" in reply.reply_text.lower()
    assert "unable" in reply.reply_text.lower() or "sorry" in reply.reply_text.lower()
    assert "contacted" not in reply.reply_text.lower()
    assert "whatsapp" not in reply.reply_text.lower()
    session.close()


def test_ordinary_clarification_does_not_trigger_handoff(isolated_db):
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "handoff_clarify"

    reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M7-CLAR-1",
            sender_id=sender,
            text="Please quote for a mechanical keyboard.",
        ),
        db=session,
    )

    assert reply.is_unsupported is False
    assert reply.needs_clarification is True
    assert reply.handoff_id is None
    assert session.scalar(
        select(HandoffModel).where(HandoffModel.sender_id == sender)
    ) is None

    reply2 = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M7-CLAR-2",
            sender_id=sender,
            text="I want to buy something but I don't know what.",
        ),
        db=session,
    )
    assert reply2.handoff_id is None
    session.close()

def test_duplicate_events_do_not_create_duplicate_handoffs(isolated_db):
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "handoff_dup"

    first = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M7-DUP-1",
            sender_id=sender,
            text="Can you order a pepperoni pizza for me?",
        ),
        db=session,
    )
    assert first.handoff_id is not None
    first_handoff_id = first.handoff_id

    second = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M7-DUP-1",
            sender_id=sender,
            text="Can you order a pepperoni pizza for me?",
        ),
        db=session,
    )
    assert second.duplicated is True
    assert second.handoff_id == first_handoff_id

    handoffs = session.scalars(
        select(HandoffModel).where(HandoffModel.sender_id == sender)
    ).all()
    assert len(handoffs) == 1
    assert handoffs[0].id == first_handoff_id
    session.close()


def test_customer_handoff_isolation(isolated_db):
    _, TestingSession = isolated_db
    session = TestingSession()
    alice = "handoff_alice"
    bob = "handoff_bob"

    alice_reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M7-ISO-A1",
            sender_id=alice,
            text="Can you order a pepperoni pizza for me?",
        ),
        db=session,
    )
    bob_reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M7-ISO-B1",
            sender_id=bob,
            text="Tell me a funny joke about programming.",
        ),
        db=session,
    )

    assert alice_reply.handoff_id is not None
    assert bob_reply.handoff_id is not None
    assert alice_reply.handoff_id != bob_reply.handoff_id

    alice_handoffs = session.scalars(
        select(HandoffModel).where(HandoffModel.sender_id == alice)
    ).all()
    bob_handoffs = session.scalars(
        select(HandoffModel).where(HandoffModel.sender_id == bob)
    ).all()

    assert len(alice_handoffs) == 1
    assert len(bob_handoffs) == 1
    assert all(h.sender_id == alice for h in alice_handoffs)
    assert all(h.sender_id == bob for h in bob_handoffs)
    assert "joke" not in alice_handoffs[0].context
    assert "pizza" not in bob_handoffs[0].context
    session.close()


def test_handoff_does_not_create_or_modify_quotation(isolated_db):
    _, TestingSession = isolated_db
    session = TestingSession()
    sender = "handoff_no_quote"

    reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M7-NOQ-1",
            sender_id=sender,
            text="Can you order a pepperoni pizza for me?",
        ),
        db=session,
    )

    assert reply.handoff_id is not None
    assert reply.enquiry_id is None
    assert reply.quotation_id is None
    assert reply.quotation_status is None
    assert session.scalar(
        select(QuotationModel).where(QuotationModel.sender_id == sender)
    ) is None
    session.close()


def test_handoff_survives_session_restart(isolated_db):
    _, TestingSession = isolated_db
    sender = "handoff_persist"

    s1 = TestingSession()
    reply = message_service.process_incoming_message(
        IncomingMessage(
            message_id="M7-PER-1",
            sender_id=sender,
            text="Can you order a pepperoni pizza for me?",
        ),
        db=s1,
    )
    s1.commit()
    handoff_id = reply.handoff_id
    s1.close()

    s2 = TestingSession()
    restored = s2.scalar(
        select(HandoffModel).where(HandoffModel.id == handoff_id)
    )
    assert restored is not None
    assert restored.sender_id == sender
    assert restored.status == "PENDING"
    assert "pizza" in restored.context
    s2.close()
