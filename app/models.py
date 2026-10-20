"""SQLAlchemy database models for QuoteMate."""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProductModel(Base):
    """Database model for product catalogue records."""

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("price > 0", name="chk_product_price_positive"),
        CheckConstraint("stock >= 0", name="chk_product_stock_non_negative"),
    )

    # Relationships
    cart_items: Mapped[list["CartItemModel"]] = relationship(
        "CartItemModel", back_populates="product", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Product(id='{self.id}', name='{self.name}', price={self.price}, stock={self.stock})>"


class ConversationModel(Base):
    """Per-sender conversation state record."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(50), default="IDLE", nullable=False)
    pending_product_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Conversation(sender_id='{self.sender_id}', state='{self.state}', pending_product_id='{self.pending_product_id}')>"


class MessageModel(Base):
    """Incoming and processed WhatsApp simulated message records.

    Idempotency is keyed on the composite ``(sender_id, message_id)`` pair, not
    on ``message_id`` alone: webhook providers (and test harnesses) may reuse
    message IDs across different senders, and one sender's reply must never be
    replayed to another sender.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    sender_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="RECEIVED", nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "sender_id", "message_id", name="uq_messages_sender_id_message_id"
        ),
    )

    def __repr__(self) -> str:
        return f"<Message(message_id='{self.message_id}', sender_id='{self.sender_id}', status='{self.status}')>"


class CartItemModel(Base):
    """Draft shopping cart item associated with a sender and product."""

    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    product_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_cart_item_quantity_positive"),
        UniqueConstraint("sender_id", "product_id", name="uq_cart_sender_product"),
    )

    # Relationships
    product: Mapped["ProductModel"] = relationship("ProductModel", back_populates="cart_items")

    def __repr__(self) -> str:
        return f"<CartItem(sender_id='{self.sender_id}', product_id='{self.product_id}', quantity={self.quantity})>"


class QuotationModel(Base):
    """Generated quotation record with financial totals and status."""

    __tablename__ = "quotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quotation_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    sender_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0.18"))
    tax: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", nullable=False)
    enquiry_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    items: Mapped[list["QuotationItemModel"]] = relationship(
        "QuotationItemModel",
        back_populates="quotation",
        cascade="all, delete-orphan",
        order_by="QuotationItemModel.id",
    )

    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="chk_quotation_subtotal_non_negative"),
        CheckConstraint("tax >= 0", name="chk_quotation_tax_non_negative"),
        CheckConstraint("total >= 0", name="chk_quotation_total_non_negative"),
        CheckConstraint("tax_rate >= 0", name="chk_quotation_tax_rate_non_negative"),
    )

    def __repr__(self) -> str:
        return (
            f"<Quotation(quotation_id='{self.quotation_id}', total={self.total}, "
            f"status='{self.status}', enquiry_id='{self.enquiry_id}')>"
        )


class QuotationItemModel(Base):
    """Snapshot of a quotation line: product, quantity, and unit price at quote time."""

    __tablename__ = "quotation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quotation_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("quotations.quotation_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    product_id: Mapped[str] = mapped_column(String(50), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    quotation: Mapped["QuotationModel"] = relationship("QuotationModel", back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_quotation_item_quantity_positive"),
        CheckConstraint("unit_price > 0", name="chk_quotation_item_unit_price_positive"),
        CheckConstraint("line_total >= 0", name="chk_quotation_item_line_total_non_negative"),
    )

    def __repr__(self) -> str:
        return (
            f"<QuotationItem(quotation_id='{self.quotation_id}', "
            f"product_id='{self.product_id}', quantity={self.quantity})>"
        )


class HandoffModel(Base):
    """Human handoff audit log for unsupported enquiries and ambiguity."""

    __tablename__ = "handoffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Handoff(id={self.id}, sender_id='{self.sender_id}', reason='{self.reason}')>"
