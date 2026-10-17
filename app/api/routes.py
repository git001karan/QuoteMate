"""API route endpoints for QuoteMate."""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    AnalyzeRequest,
    CartContents,
    ConversationSummary,
    HandoffSummary,
    IncomingMessage,
    NLPAnalysisResult,
    ProcessedMessageReply,
    Product,
)
from app.services.cart_service import cart_service
from app.services.catalogue_service import ProductNotFoundError, catalogue_service
from app.services.conversation_service import conversation_service
from app.services.handoff_service import handoff_service
from app.services.message_service import message_service
from app.services.nlp_service import nlp_service

router = APIRouter()


# --- Catalogue Endpoints -----------------------------------------------------

@router.get(
    "/products",
    response_model=List[Product],
    tags=["Catalogue"],
    summary="List all catalogue products",
)
def list_products(db: Session = Depends(get_db)) -> List[Product]:
    """Retrieve all available products from the catalogue stored in SQLite."""
    return catalogue_service.get_all_products(db=db)


@router.get(
    "/products/{product_id}",
    response_model=Product,
    tags=["Catalogue"],
    summary="Get product by ID",
    responses={404: {"description": "Product not found"}},
)
def get_product(product_id: str, db: Session = Depends(get_db)) -> Product:
    """Retrieve details for a single product by its unique product ID from SQLite."""
    try:
        return catalogue_service.get_product_by_id(product_id, db=db)
    except ProductNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


# --- NLP Diagnostics ---------------------------------------------------------

@router.post(
    "/nlp/analyze",
    response_model=NLPAnalysisResult,
    tags=["NLP Diagnostics"],
    summary="Diagnostic NLP analysis of an incoming message",
)
def analyze_message(
    payload: AnalyzeRequest, db: Session = Depends(get_db)
) -> NLPAnalysisResult:
    """Analyze customer message text for intent, matched products, and extracted quantities."""
    return nlp_service.analyze(payload.text, db=db)


# --- Messaging & Webhook Endpoints -------------------------------------------

@router.post(
    "/webhook",
    response_model=ProcessedMessageReply,
    tags=["Messaging"],
    summary="Process incoming WhatsApp webhook message",
)
@router.post(
    "/messages",
    response_model=ProcessedMessageReply,
    tags=["Messaging"],
    summary="Process incoming simulated message event (alias for webhook)",
)
def handle_incoming_message(
    payload: IncomingMessage, db: Session = Depends(get_db)
) -> ProcessedMessageReply:
    """Process an incoming WhatsApp message with duplicate protection, cart updates, and multi-turn state."""
    return message_service.process_incoming_message(payload, db=db)


# --- Cart Endpoints ----------------------------------------------------------

@router.get(
    "/cart/{sender_id}",
    response_model=CartContents,
    tags=["Cart"],
    summary="Get draft cart for a customer",
)
def get_customer_cart(sender_id: str, db: Session = Depends(get_db)) -> CartContents:
    """Retrieve the current shopping cart contents for a specific customer."""
    return cart_service.get_cart(sender_id, db=db)


@router.delete(
    "/cart/{sender_id}",
    tags=["Cart"],
    summary="Clear draft cart for a customer",
)
def clear_customer_cart(
    sender_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Remove all items from the customer's draft cart."""
    cart_service.clear_cart(sender_id, db=db)
    db.commit()
    return {"message": "Cart cleared successfully", "sender_id": sender_id}


# --- Conversation Endpoints --------------------------------------------------

@router.get(
    "/conversations",
    response_model=List[ConversationSummary],
    tags=["Conversations"],
    summary="List all customer conversations",
)
def list_conversations(
    db: Session = Depends(get_db),
) -> List[ConversationSummary]:
    """List all active conversation states ordered by last updated."""
    return conversation_service.list_all(db=db)


@router.get(
    "/conversations/{sender_id}",
    response_model=ConversationSummary,
    tags=["Conversations"],
    summary="Get conversation state for a customer",
    responses={404: {"description": "Conversation not found"}},
)
def get_customer_conversation(
    sender_id: str, db: Session = Depends(get_db)
) -> ConversationSummary:
    """Retrieve the conversational state and pending context for a specific customer."""
    conv = conversation_service.get_by_sender(sender_id, db=db)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No conversation found for sender '{sender_id}'.",
        )
    return conv


# --- Handoff Endpoints -------------------------------------------------------


@router.get(
    "/handoffs/{sender_id}",
    response_model=List[HandoffSummary],
    tags=["Handoffs"],
    summary="List human-handoff records for a customer",
)
def list_handoffs_for_sender(
    sender_id: str, db: Session = Depends(get_db)
) -> List[HandoffSummary]:
    """Return all handoff records for a sender, newest first.

    Strictly filtered by sender_id so one customer cannot view another
    customer's handoffs.
    """
    return handoff_service.get_handoffs_for_sender(sender_id, db=db)
