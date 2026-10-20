"""Data schemas for QuoteMate using Pydantic."""

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

# Characters accepted in message_id / sender_id. WhatsApp-style IDs, phone
# numbers, UUIDs, and email-like handles are all valid; anything outside this
# set (control characters, quotes, HTML, whitespace runs) is rejected with 422.
_ID_SAFE_PATTERN = re.compile(r"^[A-Za-z0-9_.:@+\-]{1,100}$")

# ISO-8601 timestamp, e.g. 2026-10-18T09:30:00Z or 2026-10-18T09:30:00+05:30
_ISO_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?"
    r"([Zz]|[+\-]\d{2}:?\d{2})?$"
)


class Product(BaseModel):
    """Pydantic model representing an authoritative catalogue product."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, description="Unique product identifier (e.g., KB-101)")
    name: str = Field(..., min_length=1, description="Product name")
    description: str = Field(..., min_length=1, description="Short product description")
    price: Decimal = Field(..., gt=0, description="Unit price in INR (must be positive)")
    stock: int = Field(..., ge=0, description="Available stock quantity (non-negative)")

    @field_validator("id", "name", "description", mode="before")
    @classmethod
    def validate_non_empty_strings(cls, v: Any) -> str:
        """Ensure string fields are non-empty after trimming."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field must be a non-empty string.")
        return v.strip()

    @field_validator("price", "stock", mode="before")
    @classmethod
    def reject_boolean_values(cls, v: Any) -> Any:
        """Prevent booleans from being cast to numeric price or stock."""
        if isinstance(v, bool):
            raise ValueError("Boolean values are not accepted for numeric fields.")
        return v

    @field_serializer("price")
    def serialize_price(self, v: Decimal) -> float:
        """Serialize Decimal price to float with 2 decimal places for JSON output."""
        return float(round(v, 2))


class MatchedProductItem(BaseModel):
    """Product matched from customer enquiry with extracted quantity and similarity score."""

    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(..., description="Authoritative catalogue product ID")
    name: str = Field(..., description="Catalogue product name")
    match_score: float = Field(..., description="RapidFuzz matching score between 0 and 100")
    extracted_quantity: Optional[int] = Field(
        None, description="Extracted quantity if explicitly provided"
    )
    quantity_missing: bool = Field(
        False, description="True if customer referenced product without specifying quantity"
    )
    is_ambiguous: bool = Field(
        False, description="True if score fell in the uncertain threshold window"
    )


class NLPAnalysisResult(BaseModel):
    """Structured result returned by the NLP understanding service."""

    model_config = ConfigDict(extra="forbid")

    original_text: str = Field(..., description="Raw incoming customer message text")
    intent: str = Field(
        ...,
        description="Predicted customer intent (e.g., quotation_request, product_inquiry, confirmation, etc.)",
    )
    intent_confidence: float = Field(
        ..., description="Model probability confidence score between 0.0 and 1.0"
    )
    matched_products: List[MatchedProductItem] = Field(
        default_factory=list, description="List of matched catalogue products"
    )
    has_missing_quantities: bool = Field(
        False, description="True if one or more matched products lacks an explicit quantity"
    )
    needs_clarification: bool = Field(
        False, description="True if model is uncertain or customer details are incomplete"
    )
    is_unsupported: bool = Field(
        False, description="True if enquiry is out-of-domain or falls below confidence threshold"
    )
    clarification_reason: Optional[str] = Field(
        None, description="Human-readable explanation of why clarification or handoff is required"
    )


class AnalyzeRequest(BaseModel):
    """Diagnostic request model to test NLP pipeline."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, description="Message string to analyze")


class IncomingMessage(BaseModel):
    """Incoming WhatsApp-style event: message ID, sender ID, timestamp and text.

    Validation contract (all violations return HTTP 422 with a clear message):
    - ``message_id`` / ``sender_id``: 1-100 characters from ``[A-Za-z0-9_.:@+-]``
      (WhatsApp-style IDs, phone numbers, UUIDs and email-like handles).
    - ``timestamp``: ISO-8601. Timezone-aware values are stored as given;
      naive values are assumed to be UTC. Garbage strings are rejected.
    - ``text``: non-empty after stripping whitespace/emoji, at most 1000 chars.
      Emoji and other unicode are accepted inside otherwise-valid text.
    """

    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(..., min_length=1, description="Unique incoming message identifier")
    sender_id: str = Field(..., min_length=1, description="Customer/sender identifier")
    text: str = Field(default="", description="Message text (may be empty)")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the incoming event",
    )

    @field_validator("message_id", "sender_id")
    @classmethod
    def validate_id_charset(cls, v: Any, info) -> str:
        """Reject empty or unsafe identifiers with an explicit 422 message."""
        field_name = info.field_name
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        value = v.strip()
        if len(value) > 100:
            raise ValueError(f"{field_name} must be at most 100 characters long.")
        if not _ID_SAFE_PATTERN.match(value):
            raise ValueError(
                f"{field_name} contains unsupported characters. Only letters, digits "
                "and _.:@+- are allowed (e.g. 'demo-user-1' or '+15551234567')."
            )
        return value

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v: Any) -> datetime:
        """Accept ISO-8601 timestamps; assume UTC for naive values; reject garbage."""
        if isinstance(v, str):
            raw = v.strip()
            if not _ISO_TIMESTAMP_PATTERN.match(raw):
                raise ValueError(
                    "timestamp must be an ISO-8601 datetime, e.g. "
                    "'2026-10-18T09:30:00Z' or '2026-10-18T09:30:00+05:30'."
                )
            v = raw.replace("Z", "+00:00").replace("z", "+00:00")
            return datetime.fromisoformat(v)
        if isinstance(v, datetime):
            if v.tzinfo is None:
                # Naive timestamps are assumed to be UTC (documented contract).
                return v.replace(tzinfo=timezone.utc)
            return v
        raise ValueError(
            "timestamp must be an ISO-8601 datetime, e.g. '2026-10-18T09:30:00Z'."
        )

    @field_validator("text", mode="before")
    @classmethod
    def validate_text(cls, v: Any) -> str:
        """Normalize text: strip edges, enforce non-empty and max length."""
        if v is None:
            return ""
        if not isinstance(v, str):
            raise ValueError("text must be a string.")
        value = v.strip()
        if len(value) > 1000:
            raise ValueError("text must be at most 1000 characters long.")
        return value


class CartLineItem(BaseModel):
    """Single line in a customer's cart with computed line total."""

    product_id: str = Field(..., description="Catalogue product ID")
    name: str = Field(..., description="Catalogue product name")
    unit_price: Decimal = Field(..., description="Unit price in INR")
    quantity: int = Field(..., ge=1, description="Requested quantity")
    line_total: Decimal = Field(..., description="unit_price * quantity")

    @field_serializer("unit_price", "line_total")
    def serialize_money(self, v: Decimal) -> float:
        """Serialize Decimal money fields to float for JSON output."""
        return float(round(v, 2))


class CartContents(BaseModel):
    """Full cart for a single sender with subtotal."""

    sender_id: str = Field(..., description="Customer/sender identifier")
    items: List[CartLineItem] = Field(default_factory=list, description="Cart line items")
    subtotal: Decimal = Field(default=Decimal("0.00"), description="Sum of all line totals")
    is_empty: bool = Field(default=True, description="True when the cart has no items")

    @field_serializer("subtotal")
    def serialize_subtotal(self, v: Decimal) -> float:
        """Serialize Decimal subtotal to float for JSON output."""
        return float(round(v, 2))


class QuotationLineBreakdown(BaseModel):
    """Single quotation line using catalogue prices (never customer-supplied amounts)."""

    product_id: str = Field(..., description="Catalogue product ID")
    name: str = Field(..., description="Catalogue product name snapshot")
    quantity: int = Field(..., ge=1, description="Requested quantity")
    unit_price: Decimal = Field(..., description="Authoritative unit price in INR")
    line_total: Decimal = Field(..., description="unit_price * quantity")

    @field_serializer("unit_price", "line_total")
    def serialize_money(self, v: Decimal) -> float:
        """Serialize Decimal money fields to float for JSON output."""
        return float(round(v, 2))


class StockIssue(BaseModel):
    """Stock or availability problem for a requested product."""

    product_id: str = Field(..., description="Requested product ID")
    name: str = Field(..., description="Product name if known, otherwise the requested ID")
    requested_quantity: int = Field(..., ge=0, description="Quantity requested by the customer")
    available_quantity: int = Field(..., ge=0, description="Current catalogue stock")
    reason: str = Field(..., description="unknown, unavailable, or insufficient_stock")


class QuotationBreakdown(BaseModel):
    """Full quotation calculation with tax, status, and optional stock issues."""

    quotation_id: Optional[str] = Field(None, description="Persisted quotation identifier")
    sender_id: str = Field(..., description="Customer/sender identifier")
    status: str = Field(..., description="DRAFT, CONFIRMED, CANCELLED, or INVALID")
    items: List[QuotationLineBreakdown] = Field(default_factory=list)
    subtotal: Decimal = Field(default=Decimal("0.00"), description="Sum of line totals")
    tax_rate: Decimal = Field(..., description="Configured tax rate as a decimal fraction")
    tax_amount: Decimal = Field(default=Decimal("0.00"), description="subtotal * tax_rate")
    total: Decimal = Field(default=Decimal("0.00"), description="subtotal + tax_amount")
    enquiry_id: Optional[str] = Field(
        None, description="Enquiry ID, present only after successful confirmation"
    )
    valid_until: Optional[datetime] = Field(
        None,
        description=(
            "Quote validity deadline (confirmation/creation time + QUOTE_VALIDITY_DAYS). "
            "Informational only; no automatic expiry is enforced."
        ),
    )
    stock_issues: List[StockIssue] = Field(default_factory=list)
    is_valid: bool = Field(False, description="True when stock and catalogue checks passed")

    @field_serializer("subtotal", "tax_amount", "total", "tax_rate")
    def serialize_decimal_fields(self, v: Decimal) -> float:
        """Serialize Decimal fields to float for JSON output."""
        return float(v)


class ProcessedMessageReply(BaseModel):
    """Structured assistant reply produced from an incoming message."""

    message_id: str = Field(..., description="Echo of the processed message ID")
    sender_id: str = Field(..., description="Customer/sender identifier")
    reply_text: str = Field(..., description="Assistant reply text")
    duplicated: bool = Field(
        False, description="True when the message ID was already processed and replayed"
    )
    intent: Optional[str] = Field(None, description="Predicted customer intent")
    intent_confidence: Optional[float] = Field(None, description="Intent confidence 0..1")
    needs_clarification: bool = Field(False, description="True when the assistant needs more info")
    is_unsupported: bool = Field(False, description="True when the request is out-of-domain")
    conversation_state: Optional[str] = Field(None, description="Current conversation state")
    cart: Optional[CartContents] = Field(None, description="Sender's cart after processing")
    quotation_id: Optional[str] = Field(None, description="Active draft or confirmed quotation ID")
    enquiry_id: Optional[str] = Field(
        None, description="Enquiry ID assigned only after successful confirmation"
    )
    quotation_status: Optional[str] = Field(None, description="Active quotation status")
    quotation: Optional[QuotationBreakdown] = Field(
        None, description="Quotation breakdown after draft calculation or confirmation"
    )
    handoff_id: Optional[int] = Field(
        None, description="Handoff record ID, present when a human handoff was created"
    )
    handoff_status: Optional[str] = Field(
        None, description="Status of the handoff record (e.g., PENDING, RESOLVED)"
    )


class HandoffSummary(BaseModel):
    """Public view of a human-handoff record for agent review."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Handoff record identifier")
    sender_id: str = Field(..., description="Customer/sender identifier")
    message_id: Optional[str] = Field(
        None, description="Originating message ID for traceability"
    )
    reason: str = Field(..., description="Reason for escalation")
    status: str = Field(..., description="Handoff status (PENDING, RESOLVED)")
    created_at: datetime = Field(..., description="Handoff creation time")


class ConversationSummary(BaseModel):
    """Public view of a per-sender conversation state record."""

    model_config = ConfigDict(from_attributes=True)

    sender_id: str = Field(..., description="Customer/sender identifier")
    state: str = Field(..., description="Current conversation state")
    pending_product_id: Optional[str] = Field(
        None, description="Catalogue product ID awaiting follow-up quantity"
    )
    created_at: datetime = Field(..., description="Conversation creation time")
    updated_at: datetime = Field(..., description="Last update time")


class TranscriptEntry(BaseModel):
    """Single turn of a customer transcript (incoming event + assistant reply)."""

    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(..., description="Incoming message identifier")
    direction: str = Field(
        ..., description="'in' for the customer event, 'out' for the assistant reply"
    )
    text: str = Field(..., description="Message or reply text")
    timestamp: datetime = Field(..., description="Event timestamp (UTC)")
    status: Optional[str] = Field(
        None, description="Processing status of the incoming event (e.g. PROCESSED)"
    )
