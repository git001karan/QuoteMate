"""Per-sender conversation state management for QuoteMate (Milestone 5)."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ConversationModel


class ConversationState:
    """Recognised conversational states for a single customer conversation."""

    IDLE = "IDLE"
    AWAITING_PRODUCT = "AWAITING_PRODUCT"
    AWAITING_QUANTITY = "AWAITING_QUANTITY"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    DECLINED = "DECLINED"


class ConversationService:
    """CRUD and state helpers for per-sender conversation records."""

    def get_or_create(self, sender_id: str, db: Optional[Session] = None) -> ConversationModel:
        """Return the existing conversation for a sender or create a new IDLE one.

        Args:
            sender_id: Unique customer/sender identifier.
            db: Optional active session.

        Returns:
            ConversationModel: The conversation record (unique per sender).
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            conversation = session.scalar(
                select(ConversationModel).where(ConversationModel.sender_id == sender_id)
            )
            if conversation is None:
                conversation = ConversationModel(
                    sender_id=sender_id, state=ConversationState.IDLE
                )
                session.add(conversation)
                if owns_session:
                    session.commit()
                    session.refresh(conversation)
                else:
                    session.flush()
            return conversation
        finally:
            if owns_session:
                session.close()

    def get_by_sender(
        self, sender_id: str, db: Optional[Session] = None
    ) -> Optional[ConversationModel]:
        """Fetch a conversation by sender, returning None when it does not exist."""
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            return session.scalar(
                select(ConversationModel).where(ConversationModel.sender_id == sender_id)
            )
        finally:
            if owns_session:
                session.close()

    def list_all(self, db: Optional[Session] = None) -> List[ConversationModel]:
        """List all conversations ordered by most recently updated first."""
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            stmt = select(ConversationModel).order_by(ConversationModel.updated_at.desc())
            return list(session.scalars(stmt).all())
        finally:
            if owns_session:
                session.close()

    def set_state(
        self,
        sender_id: str,
        state: str,
        pending_product_id: Optional[str] = None,
        context: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> ConversationModel:
        """Update the state and pending context of a sender's conversation.

        Args:
            sender_id: Unique customer identifier.
            state: Target ConversationState string.
            pending_product_id: Optional catalogue product ID awaiting follow-up.
            context: Optional contextual notes or JSON string.
            db: Optional active session.

        Returns:
            ConversationModel: The updated conversation record.
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            conversation = self.get_or_create(sender_id, db=session)
            conversation.state = state
            conversation.pending_product_id = pending_product_id
            if context is not None:
                conversation.context = context
            if owns_session:
                session.commit()
                session.refresh(conversation)
            else:
                session.flush()
            return conversation
        finally:
            if owns_session:
                session.close()

    def clear_pending(self, sender_id: str, db: Optional[Session] = None) -> ConversationModel:
        """Clear pending product and context from a sender's conversation."""
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            conversation = self.get_or_create(sender_id, db=session)
            conversation.pending_product_id = None
            conversation.context = None
            if owns_session:
                session.commit()
                session.refresh(conversation)
            else:
                session.flush()
            return conversation
        finally:
            if owns_session:
                session.close()


conversation_service = ConversationService()