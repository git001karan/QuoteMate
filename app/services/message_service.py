"""Incoming message processing for QuoteMate (Milestones 5–6).

Lifecycle per message: duplicate protection, persist event, NLP analysis,
cart update, conversation state update, draft quotation calculation,
confirmation/decline handling, and structured reply storage.

Handoff events (Milestone 7) are built on top of this lifecycle later.
"""

import logging
import re
from typing import Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import HANDOFF_CONTEXT_MESSAGES, MAX_QTY
from app.database import SessionLocal
from app.models import MessageModel, ProductModel
from app.schemas import (
    CartContents,
    IncomingMessage,
    MatchedProductItem,
    ProcessedMessageReply,
    QuotationBreakdown,
)
from app.services.cart_service import cart_service
from app.services.conversation_service import ConversationState, conversation_service
from app.services.nlp_service import nlp_service
from app.services.handoff_service import handoff_service
from app.services.quotation_service import (
    format_quotation_text,
    format_stock_issues,
    quotation_service,
)

logger = logging.getLogger("quotemate.messages")


def _filter_effective_products(
    matched_products: list[MatchedProductItem],
) -> list[MatchedProductItem]:
    """Filter out weaker category noise when a strong match exists for the same product group.

    If the user asked for 'mechanical keyboard', KB-101 is a strong match (80+). KB-102
    merely scored ~56 because of the shared word 'keyboard'. We retain KB-101 and
    prune KB-102 so the strong match is processed without false ambiguity.
    When only ambiguous matches exist (e.g. 'monitor' matching both MN-401 and MN-402),
    all candidates are preserved so clarification can be requested.
    """
    if not matched_products:
        return []

    # Group candidates by prefix (e.g. 'KB', 'MS', 'HP', 'MN', 'WC', 'HB', 'MC', 'LP')
    groups: dict[str, list[MatchedProductItem]] = {}
    for p in matched_products:
        prefix = p.product_id.split("-")[0] if "-" in p.product_id else p.product_id
        groups.setdefault(prefix, []).append(p)

    effective: list[MatchedProductItem] = []
    for prefix, candidates in groups.items():
        candidates.sort(key=lambda x: x.match_score, reverse=True)
        if len(candidates) > 1 and (candidates[0].match_score - candidates[1].match_score) < 10.0:
            # Genuine ambiguity: multiple close candidates in same group
            for c in candidates:
                if (candidates[0].match_score - c.match_score) < 10.0:
                    c.is_ambiguous = True
                    effective.append(c)
        else:
            # Single candidate or dominant candidate
            top = candidates[0]
            top.is_ambiguous = False
            effective.append(top)

    effective.sort(key=lambda x: x.match_score, reverse=True)
    return effective


def _clamp_quantity(qty: int) -> tuple[int, bool]:
    """Clamp an extracted quantity to the configured MAX_QTY.

    Returns:
        Tuple (effective_quantity, was_clamped). Word-based quantities such as
        "a hundred" are clamped by the same rule as digits.
    """
    if qty > MAX_QTY:
        return MAX_QTY, True
    return qty, False


def _format_cart(cart: CartContents) -> str:
    """Render a cart summary for a WhatsApp-style text reply."""
    if cart.is_empty:
        return "Your cart is currently empty."
    lines = ["Current Cart:"]
    for idx, item in enumerate(cart.items, start=1):
        lines.append(
            f"{idx}. {item.name} x {item.quantity} = Rs {item.line_total:,.2f}"
        )
    lines.append(f"Subtotal: Rs {cart.subtotal:,.2f}")
    return "\n".join(lines)


def _draft_reply_for_cart(
    sender_id: str, session: Session, prefix: str
) -> tuple[str, bool, QuotationBreakdown]:
    """Validate stock, persist a draft quotation, and ask for explicit confirmation."""
    breakdown = quotation_service.prepare_draft(sender_id, db=session)
    if not breakdown.is_valid:
        conversation_service.set_state(
            sender_id,
            ConversationState.AWAITING_CONFIRMATION,
            pending_product_id=None,
            context=None,
            db=session,
        )
        if breakdown.stock_issues:
            extra = format_stock_issues(breakdown.stock_issues)
        else:
            extra = "Your cart is empty, so I cannot prepare a quotation yet."
        return f"{prefix}\n\n{extra}", True, breakdown

    conversation_service.set_state(
        sender_id,
        ConversationState.AWAITING_CONFIRMATION,
        pending_product_id=None,
        context=breakdown.quotation_id,
        db=session,
    )
    text = (
        f"{prefix}\n\n{format_quotation_text(breakdown)}\n\n"
        "Please reply yes to confirm this quotation, or no to cancel. "
        "You may also add, remove, or change items before confirming."
    )
    return text, False, breakdown


class MessageService:
    """Handles the full lifecycle of incoming WhatsApp-style events."""

    def process_incoming_message(
        self, payload: IncomingMessage, db: Optional[Session] = None
    ) -> ProcessedMessageReply:
        """Process one incoming event inside an active or newly-opened session.

        Args:
            payload: Validated incoming event with message_id, sender_id, text, and timestamp.
            db: Optional active database session.

        Returns:
            ProcessedMessageReply: Structured assistant reply.
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            # --- 1. Duplicate event protection ------------------------------
            # Idempotency is keyed on the COMPOSITE (sender_id, message_id).
            # The same message_id arriving from a *different* sender is a
            # distinct event and is processed independently — one customer's
            # reply is never replayed to another customer.
            existing = session.scalar(
                select(MessageModel).where(
                    MessageModel.message_id == payload.message_id,
                    MessageModel.sender_id == payload.sender_id,
                )
            )
            if existing is not None:
                logger.info(
                    "duplicate_event message_id=%s sender_id=%s — replaying stored reply",
                    payload.message_id,
                    payload.sender_id,
                )
                cart = cart_service.get_cart(payload.sender_id, db=session)
                conv = conversation_service.get_by_sender(payload.sender_id, db=session)
                quote = quotation_service.get_active_breakdown(payload.sender_id, db=session)
                handoff = handoff_service.get_pending_handoff_for_sender(
                    payload.sender_id, db=session
                )
                return ProcessedMessageReply(
                    message_id=payload.message_id,
                    sender_id=payload.sender_id,
                    reply_text=existing.response_text
                    or "This message was already received. No action taken.",
                    duplicated=True,
                    conversation_state=conv.state if conv else None,
                    cart=cart,
                    quotation_id=quote.quotation_id if quote else None,
                    enquiry_id=quote.enquiry_id if quote else None,
                    quotation_status=quote.status if quote else None,
                    quotation=quote,
                    handoff_id=handoff.id if handoff else None,
                    handoff_status=handoff.status if handoff else None,
                )

            # Record incoming event record
            record = MessageModel(
                message_id=payload.message_id,
                sender_id=payload.sender_id,
                text=payload.text,
                timestamp=payload.timestamp,
                status="RECEIVED",
            )
            session.add(record)
            try:
                session.flush()
            except IntegrityError:
                # Concurrent race condition on the composite (sender_id, message_id)
                session.rollback()
                existing = session.scalar(
                    select(MessageModel).where(
                        MessageModel.message_id == payload.message_id,
                        MessageModel.sender_id == payload.sender_id,
                    )
                )
                cart = cart_service.get_cart(payload.sender_id, db=session)
                conv = conversation_service.get_by_sender(payload.sender_id, db=session)
                quote = quotation_service.get_active_breakdown(payload.sender_id, db=session)
                handoff = handoff_service.get_pending_handoff_for_sender(
                    payload.sender_id, db=session
                )
                return ProcessedMessageReply(
                    message_id=payload.message_id,
                    sender_id=payload.sender_id,
                    reply_text=(
                        existing.response_text
                        if existing and existing.response_text
                        else "This message was already received. No action taken."
                    ),
                    duplicated=True,
                    conversation_state=conv.state if conv else None,
                    cart=cart,
                    quotation_id=quote.quotation_id if quote else None,
                    enquiry_id=quote.enquiry_id if quote else None,
                    quotation_status=quote.status if quote else None,
                    quotation=quote,
                    handoff_id=handoff.id if handoff else None,
                    handoff_status=handoff.status if handoff else None,
                )

            # --- 2. Load / initialize conversation state ----------------------
            conv = conversation_service.get_or_create(payload.sender_id, db=session)
            user_text = (payload.text or "").strip()
            lower_text = user_text.lower()

            reply_text = ""
            intent: Optional[str] = None
            intent_confidence: Optional[float] = None
            needs_clarification = False
            is_unsupported = False
            active_quotation: Optional[QuotationBreakdown] = None
            handoff_id: Optional[int] = None
            handoff_status: Optional[str] = None

            # --- 3. Handle pending state follow-ups ---------------------------
            is_awaiting_qty = bool(
                conv.state == ConversationState.AWAITING_QUANTITY and conv.pending_product_id
            )
            new_prod_matches = (
                nlp_service.match_products(user_text, db=session) if is_awaiting_qty else []
            )
            qty, is_inv, has_qty = (
                nlp_service.extract_quantity_from_phrase(user_text)
                if is_awaiting_qty
                else (None, False, False)
            )

            if is_awaiting_qty and not (new_prod_matches and not has_qty and not is_inv):
                # Check if user cancelled
                if lower_text in ("cancel", "no", "cancel quotation", "cancel order", "stop"):
                    conversation_service.set_state(
                        payload.sender_id,
                        ConversationState.DECLINED,
                        pending_product_id=None,
                        db=session,
                    )
                    reply_text = "Your request has been cancelled."
                    intent = "decline"
                else:
                    if is_inv or (has_qty and qty is not None and qty <= 0):
                        # Zero or negative rejected
                        reply_text = (
                            "Quantity must be a positive number greater than 0. "
                            "How many units would you like?"
                        )
                        needs_clarification = True
                    elif has_qty and qty is not None and qty > 0:
                        # Successful quantity follow-up: complete pending addition
                        product = session.get(ProductModel, conv.pending_product_id)
                        if product:
                            effective_qty, was_clamped = _clamp_quantity(qty)
                            cart_service.upsert_item(
                                payload.sender_id,
                                product.id,
                                effective_qty,
                                mode="set",
                                db=session,
                            )
                            conversation_service.set_state(
                                payload.sender_id,
                                ConversationState.AWAITING_CONFIRMATION,
                                pending_product_id=None,
                                db=session,
                            )
                            cart = cart_service.get_cart(payload.sender_id, db=session)
                            clamp_note = (
                                f"\n\nNote: the maximum order quantity per item is {MAX_QTY} "
                                f"units, so I've added {effective_qty} x {product.name}."
                                if was_clamped
                                else ""
                            )
                            prefix = (
                                f"Added {effective_qty} x {product.name} to your cart."
                                f"{clamp_note}\n\n"
                                f"{_format_cart(cart)}"
                            )
                            reply_text, needs_clarification, active_quotation = (
                                _draft_reply_for_cart(payload.sender_id, session, prefix)
                            )
                        else:
                            conversation_service.set_state(
                                payload.sender_id,
                                ConversationState.IDLE,
                                pending_product_id=None,
                                db=session,
                            )
                            reply_text = "The selected product is no longer available in the catalogue."
                    else:
                        # Could not extract quantity
                        product = session.get(ProductModel, conv.pending_product_id)
                        prod_name = product.name if product else "the item"
                        reply_text = (
                            f"Please specify a valid numeric quantity for {prod_name} (e.g., 1, 2, 5)."
                        )
                        needs_clarification = True

            # --- 4. Handle Cart Management Commands ---------------------------
            elif re.search(r"\b(view|show|check|see|my|open)\s+cart\b|^\s*cart\s*$", lower_text):
                cart = cart_service.get_cart(payload.sender_id, db=session)
                reply_text = _format_cart(cart)
                intent = "product_inquiry"

            elif re.search(r"\b(clear|empty|delete|reset)\s+(the\s+)?cart\b", lower_text):
                cart_service.clear_cart(payload.sender_id, db=session)
                quotation_service.cancel_draft(payload.sender_id, db=session)
                conversation_service.set_state(
                    payload.sender_id,
                    ConversationState.IDLE,
                    pending_product_id=None,
                    context=None,
                    db=session,
                )
                reply_text = "Your cart has been cleared."
                intent = "product_inquiry"

            elif re.search(r"\b(remove|delete|drop)\b", lower_text):
                # Try matching product to remove
                matched = nlp_service.match_products(user_text, db=session)
                if matched:
                    target = matched[0]
                    removed = cart_service.remove_item(
                        payload.sender_id, target.product_id, db=session
                    )
                    cart = cart_service.get_cart(payload.sender_id, db=session)
                    if removed:
                        prefix = f"Removed {target.name} from your cart.\n\n{_format_cart(cart)}"
                        if cart.is_empty:
                            quotation_service.cancel_draft(payload.sender_id, db=session)
                            conversation_service.set_state(
                                payload.sender_id,
                                ConversationState.IDLE,
                                pending_product_id=None,
                                context=None,
                                db=session,
                            )
                            reply_text = prefix
                        else:
                            reply_text, needs_clarification, active_quotation = (
                                _draft_reply_for_cart(payload.sender_id, session, prefix)
                            )
                    else:
                        reply_text = f"{target.name} was not found in your cart.\n\n{_format_cart(cart)}"
                else:
                    reply_text = "Which product would you like to remove from your cart?"
                    needs_clarification = True

            # --- 5. NLP Analysis & Business Rule Execution -------------------
            else:
                analysis = nlp_service.analyze(user_text, db=session)
                intent = analysis.intent
                intent_confidence = analysis.intent_confidence
                needs_clarification = analysis.needs_clarification
                is_unsupported = analysis.is_unsupported

                if intent == "confirmation":
                    cart = cart_service.get_cart(payload.sender_id, db=session)
                    current_state = conv.state
                    if current_state == ConversationState.AWAITING_PRODUCT:
                        reply_text = (
                            "I still need you to specify which product you would like "
                            "before I can confirm a quotation."
                        )
                        needs_clarification = True
                    elif current_state not in (
                        ConversationState.AWAITING_CONFIRMATION,
                        ConversationState.CONFIRMED,
                    ):
                        if cart.is_empty:
                            reply_text = (
                                "Your cart is currently empty. Please add items before confirming a quotation."
                            )
                            conversation_service.set_state(
                                payload.sender_id, ConversationState.IDLE, db=session
                            )
                        else:
                            prefix = (
                                "I have a cart ready, but I need you to review the draft quotation first.\n\n"
                                f"{_format_cart(cart)}"
                            )
                            reply_text, needs_clarification, active_quotation = (
                                _draft_reply_for_cart(payload.sender_id, session, prefix)
                            )
                    else:
                        active_quotation = quotation_service.confirm_for_sender(
                            payload.sender_id, db=session
                        )
                        if not active_quotation.is_valid:
                            conversation_service.set_state(
                                payload.sender_id,
                                ConversationState.AWAITING_CONFIRMATION,
                                pending_product_id=None,
                                context=None,
                                db=session,
                            )
                            reply_text = (
                                format_stock_issues(active_quotation.stock_issues)
                                if active_quotation.stock_issues
                                else (
                                    "Your cart is currently empty. Please add items before confirming a quotation."
                                )
                            )
                            needs_clarification = True
                        else:
                            conversation_service.set_state(
                                payload.sender_id,
                                ConversationState.CONFIRMED,
                                pending_product_id=None,
                                context=active_quotation.quotation_id,
                                db=session,
                            )
                            reply_text = (
                                "Thank you! Your quotation has been confirmed.\n\n"
                                f"{format_quotation_text(active_quotation, heading='Confirmed Quotation')}\n\n"
                                "Our sales team will follow up using this enquiry ID."
                            )

                elif intent == "decline":
                    quotation_service.cancel_draft(payload.sender_id, db=session)
                    conversation_service.set_state(
                        payload.sender_id,
                        ConversationState.DECLINED,
                        pending_product_id=None,
                        context=None,
                        db=session,
                    )
                    reply_text = (
                        "Your quotation request has been cancelled. "
                        "Let us know if we can help you with anything else!"
                    )

                elif intent == "quotation_request":
                    effective_products = _filter_effective_products(analysis.matched_products)

                    # Check for zero or negative quantities in message
                    qty_val, is_neg, has_qty_flag = nlp_service.extract_quantity_from_phrase(user_text)
                    if is_neg or (has_qty_flag and qty_val is not None and qty_val <= 0):
                        reply_text = (
                            "Quantity must be a positive number greater than 0. "
                            "How many units would you like?"
                        )
                        needs_clarification = True
                        if effective_products:
                            conversation_service.set_state(
                                payload.sender_id,
                                ConversationState.AWAITING_QUANTITY,
                                pending_product_id=effective_products[0].product_id,
                                db=session,
                            )

                    elif not effective_products:
                        cart = cart_service.get_cart(payload.sender_id, db=session)
                        if not cart.is_empty:
                            prefix = (
                                "I could not identify a new catalogue product in that message, "
                                "so I will use the items already in your cart.\n\n"
                                f"{_format_cart(cart)}"
                            )
                            reply_text, needs_clarification, active_quotation = (
                                _draft_reply_for_cart(payload.sender_id, session, prefix)
                            )
                        else:
                            reply_text = (
                                "I could not identify any matching product in our catalogue. "
                                "We offer keyboards, mice, monitors, headsets, webcams, microphones, and laptop stands. "
                                "Could you please specify which product you would like?"
                            )
                            needs_clarification = True
                            conversation_service.set_state(
                                payload.sender_id, ConversationState.AWAITING_PRODUCT, db=session
                            )

                    elif any(p.is_ambiguous for p in effective_products):
                        ambiguous_names = [
                            p.name for p in effective_products if p.is_ambiguous
                        ]
                        reply_text = (
                            f"We have multiple matching products: {', '.join(ambiguous_names)}. "
                            "Could you please clarify which one you would like?"
                        )
                        needs_clarification = True
                        conversation_service.set_state(
                            payload.sender_id, ConversationState.AWAITING_PRODUCT, db=session
                        )

                    elif any(
                        p.quantity_missing or p.extracted_quantity is None
                        for p in effective_products
                    ):
                        missing_item = next(
                            p
                            for p in effective_products
                            if p.quantity_missing or p.extracted_quantity is None
                        )
                        conversation_service.set_state(
                            payload.sender_id,
                            ConversationState.AWAITING_QUANTITY,
                            pending_product_id=missing_item.product_id,
                            db=session,
                        )
                        reply_text = (
                            f"How many units of {missing_item.name} would you like to add?"
                        )
                        needs_clarification = True

                    else:
                        # All products have valid positive quantities
                        clamp_notes: list[str] = []
                        for p in effective_products:
                            if p.extracted_quantity and p.extracted_quantity > 0:
                                effective_qty, was_clamped = _clamp_quantity(
                                    p.extracted_quantity
                                )
                                cart_service.upsert_item(
                                    payload.sender_id,
                                    p.product_id,
                                    effective_qty,
                                    mode="set",
                                    db=session,
                                )
                                if was_clamped:
                                    clamp_notes.append(
                                        f"Note: the maximum order quantity per item is "
                                        f"{MAX_QTY} units, so {p.name} was added as "
                                        f"{effective_qty} units."
                                    )

                        cart = cart_service.get_cart(payload.sender_id, db=session)
                        clamp_block = (
                            "\n\n" + "\n".join(clamp_notes) if clamp_notes else ""
                        )
                        prefix = (
                            "I have added the requested items to your cart:"
                            f"{clamp_block}\n\n"
                            f"{_format_cart(cart)}"
                        )
                        reply_text, needs_clarification, active_quotation = (
                            _draft_reply_for_cart(payload.sender_id, session, prefix)
                        )

                elif intent == "product_inquiry":
                    effective_products = _filter_effective_products(analysis.matched_products)
                    if effective_products and not any(
                        p.is_ambiguous for p in effective_products
                    ):
                        details = []
                        for p in effective_products:
                            prod_record = session.get(ProductModel, p.product_id)
                            if prod_record:
                                stock_str = (
                                    f"{prod_record.stock} in stock"
                                    if prod_record.stock > 0
                                    else "out of stock"
                                )
                                details.append(
                                    f"{prod_record.name} is priced at Rs {prod_record.price:,.2f} ({stock_str})."
                                )
                        reply_text = (
                            "\n".join(details)
                            + "\n\nWould you like to prepare a quotation for this product?"
                        )
                        conversation_service.set_state(
                            payload.sender_id, ConversationState.IDLE, db=session
                        )
                    elif any(p.is_ambiguous for p in effective_products):
                        ambiguous_names = [
                            p.name for p in effective_products if p.is_ambiguous
                        ]
                        reply_text = (
                            f"We have multiple matching options: {', '.join(ambiguous_names)}. "
                            "Which model would you like to know more about?"
                        )
                        needs_clarification = True
                        conversation_service.set_state(
                            payload.sender_id, ConversationState.AWAITING_PRODUCT, db=session
                        )
                    else:
                        reply_text = (
                            "I can assist with specifications and availability for our electronics products. "
                            "Which product are you interested in?"
                        )
                        needs_clarification = True

                elif intent in ("greeting", "farewell", "thanks"):
                    # --- Friendly small-talk handling --------------------------
                    # Greetings, farewells, and thanks get an automated reply
                    # and never escalate to a human handoff. The conversation
                    # state is deliberately NOT changed so that a mid-flow
                    # "hi" or "thanks" cannot wipe a pending quotation.
                    reply_text = {
                        "greeting": (
                            "Hello! 👋 Welcome to QuoteMate. I'm your sales assistant — "
                            "I can help you browse our electronics catalogue, check "
                            "prices and stock, and prepare a quotation.\n\n"
                            "What are you looking for today?"
                        ),
                        "farewell": (
                            "Thank you for chatting with QuoteMate! When you're ready "
                            "to place an order or need a quotation, just send us a "
                            "message. Have a great day! 😊"
                        ),
                        "thanks": (
                            "You're welcome! If you'd like to adjust your quotation, "
                            "add more items, or confirm your order, I'm right here. "
                            "Happy to help! 😊"
                        ),
                    }[intent]

                elif intent == "unsupported" or is_unsupported:
                    # --- Human handoff trigger -------------------------------
                    # Only escalate genuine out-of-domain requests (is_unsupported).
                    # Ordinary clarification (missing product/quantity, ambiguity)
                    # is handled by needs_clarification without a handoff.
                    conv = conversation_service.get_by_sender(
                        payload.sender_id, db=session
                    )
                    cart = cart_service.get_cart(payload.sender_id, db=session)
                    quote = quotation_service.get_active_breakdown(
                        payload.sender_id, db=session
                    )

                    context_lines = [
                        f"Sender: {payload.sender_id}",
                        f"Event timestamp: {payload.timestamp.isoformat()}",
                        f"Latest message: {user_text}",
                        f"Reason: {analysis.clarification_reason or 'Unsupported intent'}",
                        f"Conversation state: {conv.state if conv else 'UNKNOWN'}",
                    ]
                    if conv and conv.pending_product_id:
                        context_lines.append(
                            f"Pending product: {conv.pending_product_id}"
                        )
                    if not cart.is_empty:
                        context_lines.append(f"Cart: {_format_cart(cart)}")
                    if quote is not None:
                        context_lines.append(
                            f"Active quotation: {quote.quotation_id} "
                            f"(status={quote.status}, total={quote.total})"
                        )
                    recent = session.scalars(
                        select(MessageModel)
                        .where(MessageModel.sender_id == payload.sender_id)
                        .order_by(MessageModel.id.desc())
                        .limit(HANDOFF_CONTEXT_MESSAGES)
                    ).all()
                    if recent:
                        context_lines.append("Recent conversation:")
                        for m in reversed(recent):
                            context_lines.append(f"  [in ] {m.text}")
                            if m.response_text:
                                context_lines.append(f"  [out] {m.response_text}")
                    handoff_context = "\n".join(context_lines)

                    handoff = handoff_service.create_handoff(
                        sender_id=payload.sender_id,
                        reason=analysis.clarification_reason
                        or "Unsupported request requiring human assistance.",
                        context=handoff_context,
                        message_id=payload.message_id,
                        db=session,
                    )
                    if handoff is not None:
                        handoff_id = handoff.id
                        handoff_status = handoff.status

                    reply_text = (
                        "I'm sorry, I'm unable to help with that request. "
                        "This has been passed to our human sales team for "
                        "assistance. They will get back to you shortly.\n\n"
                        "Reference: your message has been logged for review."
                    )
                    is_unsupported = True
                    needs_clarification = True

                else:
                    reply_text = (
                        "I can help you with product enquiries, prices, and quotations. "
                        "What products are you looking for today?"
                    )

            # --- 6. Persist response and update record status -----------------
            record.response_text = reply_text
            record.status = "PROCESSED"

            session.commit()

            # --- 7. Build structured reply ------------------------------------
            current_cart = cart_service.get_cart(payload.sender_id, db=session)
            final_conv = conversation_service.get_by_sender(payload.sender_id, db=session)
            if active_quotation is None:
                active_quotation = quotation_service.get_active_breakdown(
                    payload.sender_id, db=session
                )

            logger.info(
                "processed_event message_id=%s sender_id=%s intent=%s state=%s "
                "cart_items=%d enquiry_id=%s handoff_id=%s",
                payload.message_id,
                payload.sender_id,
                intent,
                final_conv.state if final_conv else None,
                len(current_cart.items),
                active_quotation.enquiry_id if active_quotation else None,
                handoff_id,
            )

            return ProcessedMessageReply(
                message_id=payload.message_id,
                sender_id=payload.sender_id,
                reply_text=reply_text,
                duplicated=False,
                intent=intent,
                intent_confidence=intent_confidence,
                needs_clarification=needs_clarification,
                is_unsupported=is_unsupported,
                conversation_state=final_conv.state if final_conv else None,
                cart=current_cart,
                quotation_id=active_quotation.quotation_id if active_quotation else None,
                enquiry_id=active_quotation.enquiry_id if active_quotation else None,
                quotation_status=active_quotation.status if active_quotation else None,
                quotation=active_quotation,
                handoff_id=handoff_id,
                handoff_status=handoff_status,
            )
        finally:
            if owns_session:
                session.close()


message_service = MessageService()




