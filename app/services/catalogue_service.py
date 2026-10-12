"""Catalogue service responsible for loading, validating, and retrieving products."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import ValidationError

from app.schemas import Product

DEFAULT_CATALOGUE_PATH = Path(__file__).resolve().parent.parent / "data" / "products.json"


class ProductNotFoundError(Exception):
    """Raised when a requested product ID is not present in the catalogue."""

    def __init__(self, product_id: str):
        super().__init__(f"Product with ID '{product_id}' was not found in the catalogue.")
        self.product_id = product_id


class CatalogueValidationError(Exception):
    """Raised when catalogue data fails structure, schema, or uniqueness validation."""

    pass


class CatalogueService:
    """In-memory catalogue service loading products from JSON source with schema validation."""

    def __init__(self, data_path: Optional[Path | str] = None):
        self.data_path = Path(data_path) if data_path else DEFAULT_CATALOGUE_PATH
        self._products: Dict[str, Product] = {}
        self.load_catalogue()

    def load_catalogue(self) -> None:
        """Load and validate products from the configured JSON file."""
        if not self.data_path.exists():
            raise CatalogueValidationError(f"Catalogue file not found at: {self.data_path}")

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except json.JSONDecodeError as err:
            raise CatalogueValidationError(f"Malformed JSON in catalogue file: {err}") from err
        except Exception as err:
            raise CatalogueValidationError(f"Failed to read catalogue file: {err}") from err

        if not isinstance(raw_data, list):
            raise CatalogueValidationError("Catalogue JSON root must be a list of products.")

        products: Dict[str, Product] = {}
        seen_ids = set()

        for idx, item in enumerate(raw_data):
            if not isinstance(item, dict):
                raise CatalogueValidationError(f"Record at index {idx} must be a dictionary.")

            try:
                product = Product.model_validate(item)
            except ValidationError as err:
                raise CatalogueValidationError(f"Validation error in record index {idx}: {err}") from err

            if product.id in seen_ids:
                raise CatalogueValidationError(f"Duplicate product ID found: '{product.id}'. Product IDs must be unique.")

            seen_ids.add(product.id)
            products[product.id] = product

        self._products = products

    def get_all_products(self) -> List[Product]:
        """Return all products in the catalogue."""
        return list(self._products.values())

    def get_product_by_id(self, product_id: str) -> Product:
        """Retrieve a single product by its unique ID, or raise ProductNotFoundError."""
        cleaned_id = product_id.strip() if product_id else ""
        product = self._products.get(cleaned_id)
        if not product:
            raise ProductNotFoundError(product_id)
        return product


# Global service instance for the default catalogue
catalogue_service = CatalogueService()
