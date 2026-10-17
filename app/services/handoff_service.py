"""Human handoff audit-log service for QuoteMate (Milestone 7).

Handles creation and retrieval of handoff records for unsupported customer
enquiries that require human-agent attention. Follows the same session
ownership and duplicate-prevention conventions as the other services.
"""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import HandoffModel


class HandoffService:
    """CRUD helpers for per-sender human-handoff records."""

    def create_handoff(
        self,
        sender_id: str,
        reason: str,
        context: str,
        message_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Optional[HandoffModel]:
        """Create a PENDING handoff record when none already exists for the sender.

        A handoff is only created when the sender does not already have a
        PENDING handoff, avoiding repeated events for the same unresolved
        issue.

        Args:
            sender_id: Unique customer/sender identifier.
            reason: Human-readable reason for escalation.
            context: Structured context for the human agent (latest message,
                conversation state, cart/quotation summary).
            message_id: Optional originating message ID for traceability.
            db: Optional active session.

        Returns:
            The created HandoffModel, or the existing PENDING handoff when one
            already exists for the sender. None on database failure.
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            # Avoid duplicate handoffs for the same unresolved issue.
            existing = session.scalar(
                select(HandoffModel).where(
                    HandoffModel.sender_id == sender_id,
                    HandoffModel.status == "PENDING",
                )
            )
            if existing is not None:
                return existing

            handoff = HandoffModel(
                sender_id=sender_id,
                message_id=message_id,
                reason=reason,
                context=context,
                status="PENDING",
                created_at=datetime.now(timezone.utc),
            )
            session.add(handoff)
            if owns_session:
                session.commit()
                session.refresh(handoff)
            else:
                session.flush()
            return handoff
        except Exception:
            if owns_session:
                session.rollback()
            return None
        finally:
            if owns_session:
                session.close()

    def get_handoffs_for_sender(
        self, sender_id: str, db: Optional[Session] = None
    ) -> List[HandoffModel]:
        """Return all handoff records for a sender, newest first.

        Strictly filtered by sender_id so one customer cannot view another
        customer's handoffs.
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            stmt = (
                select(HandoffModel)
                .where(HandoffModel.sender_id == sender_id)
                .order_by(HandoffModel.created_at.desc())
            )
            return list(session.scalars(stmt).all())
        finally:
            if owns_session:
                session.close()

    def get_pending_handoff_for_sender(
        self, sender_id: str, db: Optional[Session] = None
    ) -> Optional[HandoffModel]:
        """Return the sender's current PENDING handoff, if any."""
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            return session.scalar(
                select(HandoffModel).where(
                    HandoffModel.sender_id == sender_id,
                    HandoffModel.status == "PENDING",
                )
            )
        finally:
            if owns_session:
                session.close()

    def mark_resolved(
        self, handoff_id: int, db: Optional[Session] = None
    ) -> Optional[HandoffModel]:
        """Mark a handoff as resolved (human agent has responded)."""
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            handoff = session.get(HandoffModel, handoff_id)
            if handoff is None:
                return None
            handoff.status = "RESOLVED"
            if owns_session:
                session.commit()
                session.refresh(handoff)
            else:
                session.flush()
            return handoff
        finally:
            if owns_session:
                session.close()


# Global handoff service instance
handoff_service = HandoffService()
