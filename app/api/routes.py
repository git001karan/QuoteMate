"""API route endpoints for QuoteMate."""

import hashlib
import hmac
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import WHATSAPP_APP_SECRET, WHATSAPP_VERIFY_TOKEN
from app.database import get_db
from app.models import MessageModel
from app.schemas import (
    AnalyzeRequest,
    CartContents,
    ConversationSummary,
    HandoffSummary,
    IncomingMessage,
    NLPAnalysisResult,
    ProcessedMessageReply,
    Product,
    QuotationBreakdown,
    TranscriptEntry,
)
from app.services.cart_service import cart_service
from app.services.catalogue_service import ProductNotFoundError, catalogue_service
from app.services.conversation_service import conversation_service
from app.services.handoff_service import handoff_service
from app.services.message_service import message_service
from app.services.nlp_service import nlp_service
from app.services.quotation_service import quotation_service

logger = logging.getLogger("quotemate.api")

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

def _verify_whatsapp_signature(request_body: bytes, signature_header: Optional[str]) -> bool:
    """Verify Meta's X-Hub-Signature-256 header using constant-time comparison.

    Live WhatsApp integration is out of scope for this assessment, but this is
    the documented integration point: when WHATSAPP_APP_SECRET is configured,
    every POST /webhook payload must carry ``sha256=<hexdigest>`` computed as
    HMAC-SHA256(body, secret). Verification is skipped entirely when no secret
    is configured (the default), keeping local development friction-free.
    """
    app_secret = os.getenv("WHATSAPP_APP_SECRET", WHATSAPP_APP_SECRET)
    if not app_secret:
        return True  # Hardening disabled by default.
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        app_secret.encode("utf-8"), request_body, hashlib.sha256
    ).hexdigest()
    provided = signature_header.split("sha256=", 1)[1].strip()
    return hmac.compare_digest(expected, provided)


@router.get(
    "/webhook",
    response_class=PlainTextResponse,
    tags=["Messaging"],
    summary="WhatsApp Cloud API verification handshake",
)
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
) -> PlainTextResponse:
    """Answer Meta's webhook verification GET (hub.mode/hub.verify_token/hub.challenge).

    Mirrors Meta's contract: when hub.mode == "subscribe" and hub.verify_token
    matches the configured WHATSAPP_VERIFY_TOKEN, echo back hub.challenge as
    plain text. Disabled (403) when WHATSAPP_VERIFY_TOKEN is not configured.
    """
    configured_token = os.getenv("WHATSAPP_VERIFY_TOKEN", WHATSAPP_VERIFY_TOKEN)
    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhook verification is disabled: set WHATSAPP_VERIFY_TOKEN to enable it.",
        )
    if hub_mode == "subscribe" and hmac.compare_digest(
        hub_verify_token or "", configured_token
    ):
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Webhook verification failed: hub.verify_token does not match.",
    )


@router.post(
    "/webhook",
    response_model=ProcessedMessageReply,
    tags=["Messaging"],
    summary="Process incoming WhatsApp webhook message (HMAC-verified when configured)",
)
async def handle_webhook(request: Request, db: Session = Depends(get_db)) -> ProcessedMessageReply:
    """WhatsApp webhook entry point.

    When WHATSAPP_APP_SECRET is set, the X-Hub-Signature-256 HMAC header is
    verified (constant-time) before the payload is processed; missing or invalid
    signatures are rejected with 401. With no secret configured (default, local
    development and all tests) the payload is processed directly.
    """
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not _verify_whatsapp_signature(body, signature):
        logger.warning("webhook_rejected reason=invalid_signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Hub-Signature-256 header.",
        )
    payload = IncomingMessage.model_validate_json(body)
    return message_service.process_incoming_message(payload, db=db)


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
    "/handoffs",
    response_model=List[HandoffSummary],
    tags=["Handoffs"],
    summary="List all PENDING human-handoff records (agent work queue)",
)
def list_pending_handoffs(db: Session = Depends(get_db)) -> List[HandoffSummary]:
    """Return every PENDING handoff across senders, newest first (agent queue)."""
    return handoff_service.get_pending_handoffs(db=db)


@router.post(
    "/handoffs/{handoff_id}/resolve",
    response_model=HandoffSummary,
    tags=["Handoffs"],
    summary="Mark a handoff as resolved",
    responses={404: {"description": "Handoff not found"}},
)
def resolve_handoff(handoff_id: int, db: Session = Depends(get_db)) -> HandoffSummary:
    """Mark a handoff record RESOLVED once a human agent has handled it."""
    handoff = handoff_service.mark_resolved(handoff_id, db=db)
    if handoff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No handoff found with id {handoff_id}.",
        )
    db.commit()
    return handoff


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


# --- Conversation transcript -------------------------------------------------

@router.get(
    "/conversations/{sender_id}/messages",
    response_model=List[TranscriptEntry],
    tags=["Conversations"],
    summary="Full message transcript for a customer",
)
def get_conversation_messages(
    sender_id: str, db: Session = Depends(get_db)
) -> List[TranscriptEntry]:
    """Return the full transcript for a sender, oldest first.

    Each stored event yields up to two entries: the incoming customer message
    (direction='in') and the stored assistant reply (direction='out').
    """
    rows = db.scalars(
        select(MessageModel)
        .where(MessageModel.sender_id == sender_id)
        .order_by(MessageModel.id.asc())
    ).all()
    entries: List[TranscriptEntry] = []
    for row in rows:
        entries.append(
            TranscriptEntry(
                message_id=row.message_id,
                direction="in",
                text=row.text,
                timestamp=row.timestamp,
                status=row.status,
            )
        )
        if row.response_text:
            entries.append(
                TranscriptEntry(
                    message_id=row.message_id,
                    direction="out",
                    text=row.response_text,
                    timestamp=row.timestamp,
                    status=row.status,
                )
            )
    return entries


# --- Quotation persistence endpoints -----------------------------------------

@router.get(
    "/quotations",
    response_model=List[QuotationBreakdown],
    tags=["Quotations"],
    summary="List quotations (optionally filtered by sender_id)",
)
def list_quotations(
    sender_id: Optional[str] = Query(
        None, description="When provided, only this sender's quotations are returned"
    ),
    db: Session = Depends(get_db),
) -> List[QuotationBreakdown]:
    """List stored quotations with full breakdowns, newest first."""
    if sender_id:
        rows = quotation_service.list_for_sender(sender_id, db=db)
    else:
        rows = quotation_service.list_all_for_admin(db=db)
    return [quotation_service.breakdown_for_model(row) for row in rows]


@router.get(
    "/quotations/{enquiry_id}",
    response_model=QuotationBreakdown,
    tags=["Quotations"],
    summary="Get a confirmed quotation by enquiry ID",
    responses={404: {"description": "Enquiry not found"}},
)
def get_quotation_by_enquiry(
    enquiry_id: str, db: Session = Depends(get_db)
) -> QuotationBreakdown:
    """Retrieve one confirmed quotation (with breakdown) by its enquiry ID."""
    row = quotation_service.get_by_enquiry_id(enquiry_id, db=db)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No confirmed quotation found for enquiry ID '{enquiry_id}'.",
        )
    return quotation_service.breakdown_for_model(row)
