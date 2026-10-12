"""Catalogue service with SQLite persistence and idempotent JSON seeding."""

import json
from pathlib import Path
from typing import List, Optional
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ProductModel
from app.schemas import Product

DEFAULT_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "products.json"


class ProductNotFoundError(Exception):
    """Raised when a requested product ID is not present in the catalogue."""

    def __init__(self, product_id: str):
        super().__init__(f"Product with ID '{product_id}' was not found in the catalogue.")
        self.product_id = product_id


class CatalogueValidationError(Exception):
    """Raised when catalogue data fails structure, schema, or uniqueness validation."""

    pass


class CatalogueService:
    """Service managing product catalogue records backed by SQLite database."""

    def __init__(
        self,
        seed_path: Optional[Path | str] = None,
        data_path: Optional[Path | str] = None,
        validate_on_init: bool = True,
    ):
        self.seed_path = Path(seed_path or data_path or DEFAULT_SEED_PATH)
        if validate_on_init:
            # Validates seed file format immediately to catch syntax or schema errors early
            self.load_seed_products()

    def load_catalogue(self) -> List[Product]:
        """Backward-compatible alias for load_seed_products."""
        return self.load_seed_products()

    def load_seed_products(self, path: Optional[Path | str] = None) -> List[Product]:
        """Read and validate product records from a JSON file.

        Args:
            path: Optional custom path to JSON file. Defaults to self.seed_path.

        Returns:
            List[Product]: List of validated Pydantic Product instances.

        Raises:
            CatalogueValidationError: If the file is missing, malformed, or contains duplicates.
        """
        target_path = Path(path) if path else self.seed_path
        if not target_path.exists():
            raise CatalogueValidationError(f"Seed file not found at: {target_path}")

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except json.JSONDecodeError as err:
            raise CatalogueValidationError(f"Malformed JSON in catalogue file: {err}") from err
        except Exception as err:
            raise CatalogueValidationError(f"Failed to read catalogue file: {err}") from err

        if not isinstance(raw_data, list):
            raise CatalogueValidationError("Catalogue JSON root must be a list of products.")

        products: List[Product] = []
        seen_ids = set()

        for idx, item in enumerate(raw_data):
            if not isinstance(item, dict):
                raise CatalogueValidationError(f"Record at index {idx} must be a dictionary.")

            try:
                product = Product.model_validate(item)
            except ValidationError as err:
                raise CatalogueValidationError(f"Validation error in record index {idx}: {err}") from err

            if product.id in seen_ids:
                raise CatalogueValidationError(
                    f"Duplicate product ID found: '{product.id}'. Product IDs must be unique."
                )

            seen_ids.add(product.id)
            products.append(product)

        return products

    def seed_catalogue_if_empty(
        self, db: Optional[Session] = None, seed_path: Optional[Path | str] = None
    ) -> int:
        """Idempotently seed products from JSON into the database.

        Rules:
        - Only inserts products whose ID is not already present in the database.
        - Never resets or overwrites existing product prices, descriptions, or stock.
        - Re-running initialization creates 0 duplicate products.

        Args:
            db: Optional active Session. If omitted, a temporary session is opened and closed.
            seed_path: Optional path to custom seed file.

        Returns:
            int: Number of newly inserted products.
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            seed_items = self.load_seed_products(seed_path)
            existing_ids = set(session.scalars(select(ProductModel.id)).all())

            new_count = 0
            for item in seed_items:
                if item.id not in existing_ids:
                    db_product = ProductModel(
                        id=item.id,
                        name=item.name,
                        description=item.description,
                        price=item.price,
                        stock=item.stock,
                    )
                    session.add(db_product)
                    existing_ids.add(item.id)
                    new_count += 1

            if new_count > 0:
                session.commit()
            return new_count
        except Exception:
            session.rollback()
            raise
        finally:
            if owns_session:
                session.close()

    def get_all_products(self, db: Optional[Session] = None) -> List[Product]:
        """Retrieve all catalogue products from the SQLite database.

        Args:
            db: Optional active Session. If omitted, a temporary session is used.

        Returns:
            List[Product]: List of products as Pydantic models.
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            stmt = select(ProductModel).order_by(ProductModel.id)
            models = session.scalars(stmt).all()
            return [
                Product(
                    id=m.id,
                    name=m.name,
                    description=m.description,
                    price=m.price,
                    stock=m.stock,
                )
                for m in models
            ]
        finally:
            if owns_session:
                session.close()

    def get_product_by_id(self, product_id: str, db: Optional[Session] = None) -> Product:
        """Retrieve a single product by ID from SQLite, or raise ProductNotFoundError.

        Args:
            product_id: Unique product identifier.
            db: Optional active Session. If omitted, a temporary session is used.

        Returns:
            Product: Matching product Pydantic model.

        Raises:
            ProductNotFoundError: If the product ID is not found.
        """
        cleaned_id = product_id.strip() if product_id else ""
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            stmt = select(ProductModel).where(ProductModel.id == cleaned_id)
            model = session.scalar(stmt)
            if not model:
                raise ProductNotFoundError(product_id)
            return Product(
                id=model.id,
                name=model.name,
                description=model.description,
                price=model.price,
                stock=model.stock,
            )
        finally:
            if owns_session:
                session.close()


# Global catalogue service instance
catalogue_service = CatalogueService()
