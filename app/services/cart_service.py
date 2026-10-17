"""Per-customer cart management for QuoteMate (Milestone 5)."""

from decimal import Decimal
from typing import Optional
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import CartItemModel, ProductModel
from app.schemas import CartContents, CartLineItem
from app.services.catalogue_service import ProductNotFoundError


class CartService:
    """Independent shopping carts keyed by sender_id, backed by SQLite."""

    def upsert_item(
        self,
        sender_id: str,
        product_id: str,
        quantity: int,
        mode: str = "set",
        db: Optional[Session] = None,
    ) -> CartItemModel:
        """Add a product to a sender's cart or update the quantity if already present.

        Behavior for repeated additions:
            - When `mode="set"` (default): The quantity is set to the latest explicit
              value specified by the customer. This ensures idempotent and predictable
              behavior when re-stating a quantity or completing a follow-up.
            - When `mode="add"`: The quantity is incremented by the specified amount.

        Args:
            sender_id: Unique customer/sender identifier.
            product_id: Existing catalogue product ID.
            quantity: Positive integer quantity (must be > 0).
            mode: "set" to overwrite quantity, or "add" to increment.
            db: Optional active session.

        Returns:
            CartItemModel: The persisted cart item record.

        Raises:
            ValueError: If quantity is less than or equal to 0.
            ProductNotFoundError: If the product_id does not exist in the catalogue.
        """
        if quantity <= 0:
            raise ValueError("Cart item quantity must be positive.")

        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            # Verify product exists in database catalogue
            product = session.get(ProductModel, product_id)
            if product is None:
                raise ProductNotFoundError(product_id)

            item = session.scalar(
                select(CartItemModel).where(
                    CartItemModel.sender_id == sender_id,
                    CartItemModel.product_id == product_id,
                )
            )
            if item is None:
                item = CartItemModel(sender_id=sender_id, product_id=product_id, quantity=quantity)
                session.add(item)
            else:
                if mode == "add":
                    item.quantity += quantity
                else:
                    item.quantity = quantity

            if owns_session:
                session.commit()
                session.refresh(item)
            else:
                session.flush()
            return item
        finally:
            if owns_session:
                session.close()

    def remove_item(
        self, sender_id: str, product_id: str, db: Optional[Session] = None
    ) -> bool:
        """Remove a single product from a sender's cart.

        Args:
            sender_id: Unique customer identifier.
            product_id: Product ID to remove.
            db: Optional active session.

        Returns:
            bool: True if an item was found and deleted, False otherwise.
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            result = session.execute(
                delete(CartItemModel).where(
                    CartItemModel.sender_id == sender_id,
                    CartItemModel.product_id == product_id,
                )
            )
            if owns_session:
                session.commit()
            else:
                session.flush()
            return (result.rowcount or 0) > 0
        finally:
            if owns_session:
                session.close()

    def get_cart(self, sender_id: str, db: Optional[Session] = None) -> CartContents:
        """Return the full cart for a sender with line totals and subtotal.

        Strictly filtered by sender_id to ensure customer cart isolation.

        Args:
            sender_id: Unique customer identifier.
            db: Optional active session.

        Returns:
            CartContents: Structured cart contents with line items and subtotal.
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            rows = session.execute(
                select(CartItemModel, ProductModel)
                .join(ProductModel, CartItemModel.product_id == ProductModel.id)
                .where(CartItemModel.sender_id == sender_id)
                .order_by(ProductModel.id)
            ).all()

            items: list[CartLineItem] = []
            for cart_item, product in rows:
                line_total = (product.price * cart_item.quantity).quantize(Decimal("0.01"))
                items.append(
                    CartLineItem(
                        product_id=cart_item.product_id,
                        name=product.name,
                        unit_price=product.price,
                        quantity=cart_item.quantity,
                        line_total=line_total,
                    )
                )

            subtotal = sum((item.line_total for item in items), Decimal("0.00")).quantize(
                Decimal("0.01")
            )
            return CartContents(
                sender_id=sender_id,
                items=items,
                subtotal=subtotal,
                is_empty=len(items) == 0,
            )
        finally:
            if owns_session:
                session.close()

    def clear_cart(self, sender_id: str, db: Optional[Session] = None) -> None:
        """Remove every item from a sender's cart.

        Args:
            sender_id: Unique customer identifier.
            db: Optional active session.
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            session.execute(
                delete(CartItemModel).where(CartItemModel.sender_id == sender_id)
            )
            if owns_session:
                session.commit()
            else:
                session.flush()
        finally:
            if owns_session:
                session.close()


cart_service = CartService()