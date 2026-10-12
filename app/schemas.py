"""Data schemas for QuoteMate using Pydantic."""

from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


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
