"""Data schemas for QuoteMate using Pydantic."""

from decimal import Decimal
from typing import Any
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
