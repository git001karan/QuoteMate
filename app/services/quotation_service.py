"""Quotation calculation, stock validation, and confirmation (Milestone 6).

Prices and stock are always read from the authoritative SQLite catalogue.
Customer-supplied amounts are never used. Draft calculation does not
decrement inventory; stock is reduced only after a successful confirmation.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
import uuid

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import DEFAULT_TAX_RATE, QUOTE_VALIDITY_DAYS
from app.database import SessionLocal
from app.models import ProductModel, QuotationItemModel, QuotationModel
from app.schemas import QuotationBreakdown, QuotationLineBreakdown, StockIssue
from app.services.cart_service import cart_service

MONEY = Decimal("0.01")
TAX_RATE_QUANT = Decimal("0.0001")


class QuotationStatus:
    """Persisted quotation lifecycle statuses."""

    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    INVALID = "INVALID"


def money(value: Decimal | int | str) -> Decimal:
    """Round a monetary value to two decimal places using half-up rounding."""
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def configured_tax_rate() -> Decimal:
    """Return the configured tax rate as Decimal without float artefacts."""
    return Decimal(str(DEFAULT_TAX_RATE)).quantize(TAX_RATE_QUANT, rounding=ROUND_HALF_UP)


def _new_quotation_id() -> str:
    return f"QT-{uuid.uuid4().hex[:12].upper()}"


def _new_enquiry_id() -> str:
    return f"ENQ-{uuid.uuid4().hex[:12].upper()}"


def format_quotation_text(breakdown: QuotationBreakdown, *, heading: str | None = None) -> str:
    """Render a customer-facing quotation summary."""
    title = heading or (
        "Confirmed Quotation"
        if breakdown.status == QuotationStatus.CONFIRMED
        else "Draft Quotation"
    )
    lines = [f"{title} ({breakdown.quotation_id}):"] if breakdown.quotation_id else [f"{title}:"]
    for idx, item in enumerate(breakdown.items, start=1):
        lines.append(
            f"{idx}. {item.name} ({item.product_id}) x {item.quantity} "
            f"@ Rs {item.unit_price:,.2f} = Rs {item.line_total:,.2f}"
        )
    tax_pct = (breakdown.tax_rate * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    lines.append(f"Subtotal: Rs {breakdown.subtotal:,.2f}")
    lines.append(f"Tax ({tax_pct.normalize()}%): Rs {breakdown.tax_amount:,.2f}")
    lines.append(f"Total: Rs {breakdown.total:,.2f}")
    if breakdown.enquiry_id:
        lines.append(f"Enquiry ID: {breakdown.enquiry_id}")
    if breakdown.valid_until:
        lines.append(
            f"Quote valid until: {breakdown.valid_until.strftime('%Y-%m-%d %H:%M UTC')}"
        )
    return "\n".join(lines)


def format_stock_issues(issues: list[StockIssue]) -> str:
    """Render stock/availability problems without substituting products."""
    lines = ["I cannot prepare a quotation for the following items:"]
    for issue in issues:
        if issue.reason == "unknown":
            lines.append(f"- {issue.product_id}: this product is not in our catalogue.")
        elif issue.reason == "unavailable":
            lines.append(
                f"- {issue.name} ({issue.product_id}): currently unavailable "
                f"(requested {issue.requested_quantity}, available 0)."
            )
        else:
            lines.append(
                f"- {issue.name} ({issue.product_id}): insufficient stock "
                f"(requested {issue.requested_quantity}, available {issue.available_quantity})."
            )
    lines.append("No enquiry ID has been created. Please adjust quantities or choose other products.")
    return "\n".join(lines)


class QuotationService:
    """Catalogue-backed quotation calculation and confirmation workflow."""

    def evaluate_items(
        self,
        sender_id: str,
        requested_items: list[tuple[str, int]],
        db: Session,
        *,
        persist_draft: bool = False,
    ) -> QuotationBreakdown:
        """Validate stock and calculate totals from authoritative catalogue rows.

        Args:
            sender_id: Customer identifier (used for persistence and isolation).
            requested_items: List of (product_id, quantity) pairs.
            db: Active database session.
            persist_draft: When True and validation passes, upsert a DRAFT quotation.

        Returns:
            QuotationBreakdown with line items, tax, totals, and any stock issues.
        """
        tax_rate = configured_tax_rate()
        issues: list[StockIssue] = []
        lines: list[QuotationLineBreakdown] = []

        if not requested_items:
            if persist_draft:
                self.cancel_draft(sender_id, db=db)
            return QuotationBreakdown(
                quotation_id=None,
                sender_id=sender_id,
                status=QuotationStatus.INVALID,
                items=[],
                subtotal=money(Decimal("0.00")),
                tax_rate=tax_rate,
                tax_amount=money(Decimal("0.00")),
                total=money(Decimal("0.00")),
                enquiry_id=None,
                stock_issues=[],
                is_valid=False,
            )

        # Lock catalogue rows involved in this evaluation so confirmation is consistent.
        product_ids = [pid for pid, _ in requested_items]
        products_by_id: dict[str, ProductModel] = {}
        if product_ids:
            rows = db.scalars(
                select(ProductModel).where(ProductModel.id.in_(product_ids)).with_for_update()
            ).all()
            products_by_id = {p.id: p for p in rows}

        for product_id, quantity in requested_items:
            product = products_by_id.get(product_id)
            if product is None:
                issues.append(
                    StockIssue(
                        product_id=product_id,
                        name=product_id,
                        requested_quantity=max(quantity, 0),
                        available_quantity=0,
                        reason="unknown",
                    )
                )
                continue

            available = int(product.stock)
            if available <= 0:
                issues.append(
                    StockIssue(
                        product_id=product.id,
                        name=product.name,
                        requested_quantity=quantity,
                        available_quantity=available,
                        reason="unavailable",
                    )
                )
                continue

            if quantity > available:
                issues.append(
                    StockIssue(
                        product_id=product.id,
                        name=product.name,
                        requested_quantity=quantity,
                        available_quantity=available,
                        reason="insufficient_stock",
                    )
                )
                continue

            unit_price = money(product.price)
            line_total = money(unit_price * quantity)
            lines.append(
                QuotationLineBreakdown(
                    product_id=product.id,
                    name=product.name,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )

        if issues:
            if persist_draft:
                self.cancel_draft(sender_id, db=db)
            return QuotationBreakdown(
                quotation_id=None,
                sender_id=sender_id,
                status=QuotationStatus.INVALID,
                items=[],
                subtotal=money(Decimal("0.00")),
                tax_rate=tax_rate,
                tax_amount=money(Decimal("0.00")),
                total=money(Decimal("0.00")),
                enquiry_id=None,
                stock_issues=issues,
                is_valid=False,
            )

        subtotal = money(sum((line.line_total for line in lines), Decimal("0.00")))
        tax_amount = money(subtotal * tax_rate)
        total = money(subtotal + tax_amount)

        quotation_id: Optional[str] = None
        if persist_draft:
            quotation_id = self._upsert_draft(
                sender_id=sender_id,
                lines=lines,
                subtotal=subtotal,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                total=total,
                db=db,
            )

        return QuotationBreakdown(
            quotation_id=quotation_id,
            sender_id=sender_id,
            status=QuotationStatus.DRAFT,
            items=lines,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total=total,
            enquiry_id=None,
            stock_issues=[],
            is_valid=True,
        )

    def prepare_draft(self, sender_id: str, db: Optional[Session] = None) -> QuotationBreakdown:
        """Validate the sender's cart and persist a draft quotation when valid.

        Does not decrement inventory. Does not generate an enquiry ID.
        Recalculates an existing draft in place when the cart changes.
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            cart = cart_service.get_cart(sender_id, db=session)
            if cart.is_empty:
                self.cancel_draft(sender_id, db=session)
                return QuotationBreakdown(
                    quotation_id=None,
                    sender_id=sender_id,
                    status=QuotationStatus.INVALID,
                    items=[],
                    subtotal=money(Decimal("0.00")),
                    tax_rate=configured_tax_rate(),
                    tax_amount=money(Decimal("0.00")),
                    total=money(Decimal("0.00")),
                    enquiry_id=None,
                    stock_issues=[],
                    is_valid=False,
                )

            requested = [(item.product_id, item.quantity) for item in cart.items]
            result = self.evaluate_items(
                sender_id, requested, session, persist_draft=True
            )
            if owns_session:
                session.commit()
            return result
        finally:
            if owns_session:
                session.close()

    def confirm_for_sender(self, sender_id: str, db: Optional[Session] = None) -> QuotationBreakdown:
        """Revalidate stock and prices, then persist a confirmed quotation with an enquiry ID.

        Repeated confirmation of the same draft returns the existing enquiry ID.
        Another sender cannot confirm this quotation.
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            cart = cart_service.get_cart(sender_id, db=session)
            requested = [(item.product_id, item.quantity) for item in cart.items]
            existing_confirmed = self._latest_confirmed(sender_id, db=session)

            # Repeated confirmation of an unchanged cart must not create a second enquiry.
            if existing_confirmed is not None and self._cart_matches_quotation(
                requested, existing_confirmed
            ):
                return self._to_breakdown(existing_confirmed, is_valid=True)

            evaluated = self.evaluate_items(
                sender_id, requested, session, persist_draft=False
            )
            if not evaluated.is_valid:
                return evaluated

            nested = session.begin_nested()
            try:
                draft = self._active_draft(sender_id, db=session)
                if draft is None:
                    self._upsert_draft(
                        sender_id=sender_id,
                        lines=evaluated.items,
                        subtotal=evaluated.subtotal,
                        tax_rate=evaluated.tax_rate,
                        tax_amount=evaluated.tax_amount,
                        total=evaluated.total,
                        db=session,
                    )
                    draft = self._active_draft(sender_id, db=session)
                    if draft is None:
                        nested.commit()
                        return evaluated

                self._replace_items(draft, evaluated.items, session)
                draft.subtotal = evaluated.subtotal
                draft.tax_rate = evaluated.tax_rate
                draft.tax = evaluated.tax_amount
                draft.total = evaluated.total
                draft.status = QuotationStatus.CONFIRMED
                draft.confirmed_at = datetime.now(timezone.utc)
                draft.updated_at = datetime.now(timezone.utc)
                if not draft.enquiry_id:
                    draft.enquiry_id = _new_enquiry_id()

                product_ids = [line.product_id for line in evaluated.items]
                products = {
                    p.id: p
                    for p in session.scalars(
                        select(ProductModel)
                        .where(ProductModel.id.in_(product_ids))
                        .with_for_update()
                    ).all()
                }
                for line in evaluated.items:
                    product = products[line.product_id]
                    product.stock = int(product.stock) - line.quantity

                session.flush()
                nested.commit()
            except IntegrityError:
                nested.rollback()
                confirmed = self._latest_confirmed(sender_id, db=session)
                if confirmed is not None and self._cart_matches_quotation(
                    requested, confirmed
                ):
                    return self._to_breakdown(confirmed, is_valid=True)
                raise

            if owns_session:
                session.commit()
            session.refresh(draft)
            return self._to_breakdown(draft, is_valid=True)
        finally:
            if owns_session:
                session.close()

    def cancel_draft(self, sender_id: str, db: Optional[Session] = None) -> int:
        """Cancel the sender's pending draft quotation without creating an enquiry ID.

        Confirmed quotations are left unchanged so historical enquiry IDs are preserved.
        """
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            drafts = session.scalars(
                select(QuotationModel).where(
                    QuotationModel.sender_id == sender_id,
                    QuotationModel.status == QuotationStatus.DRAFT,
                )
            ).all()
            cancelled = 0
            for draft in drafts:
                draft.status = QuotationStatus.CANCELLED
                draft.updated_at = datetime.now(timezone.utc)
                # Enquiry IDs are never assigned to drafts; keep them null.
                cancelled += 1
            if owns_session:
                session.commit()
            else:
                session.flush()
            return cancelled
        finally:
            if owns_session:
                session.close()

    def get_for_sender(
        self, quotation_id: str, sender_id: str, db: Optional[Session] = None
    ) -> Optional[QuotationModel]:
        """Load a quotation only when it belongs to the given sender."""
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            return session.scalar(
                select(QuotationModel).where(
                    QuotationModel.quotation_id == quotation_id,
                    QuotationModel.sender_id == sender_id,
                )
            )
        finally:
            if owns_session:
                session.close()

    def get_active_breakdown(
        self, sender_id: str, db: Optional[Session] = None
    ) -> Optional[QuotationBreakdown]:
        """Return the sender's draft quotation, or their latest confirmed one."""
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            draft = self._active_draft(sender_id, db=session)
            if draft is not None:
                return self._to_breakdown(draft, is_valid=True)
            confirmed = self._latest_confirmed(sender_id, db=session)
            if confirmed is not None:
                return self._to_breakdown(confirmed, is_valid=True)
            return None
        finally:
            if owns_session:
                session.close()

    def list_for_sender(
        self, sender_id: str, db: Optional[Session] = None
    ) -> list[QuotationModel]:
        """Return all quotations for a sender, newest first."""
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            return list(
                session.scalars(
                    select(QuotationModel)
                    .where(QuotationModel.sender_id == sender_id)
                    .order_by(QuotationModel.created_at.desc())
                ).all()
            )
        finally:
            if owns_session:
                session.close()

    def get_by_enquiry_id(
        self, enquiry_id: str, db: Optional[Session] = None
    ) -> Optional[QuotationModel]:
        """Return the confirmed quotation carrying the given enquiry ID."""
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            return session.scalar(
                select(QuotationModel)
                .options(selectinload(QuotationModel.items))
                .where(QuotationModel.enquiry_id == enquiry_id)
            )
        finally:
            if owns_session:
                session.close()

    def list_all_for_admin(
        self, db: Optional[Session] = None
    ) -> list[QuotationModel]:
        """Return every quotation (all senders), newest first. Admin/inspection use."""
        owns_session = False
        session = db
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            return list(
                session.scalars(
                    select(QuotationModel)
                    .options(selectinload(QuotationModel.items))
                    .order_by(QuotationModel.created_at.desc())
                ).all()
            )
        finally:
            if owns_session:
                session.close()

    def breakdown_for_model(self, quotation: QuotationModel) -> QuotationBreakdown:
        """Public helper: convert a stored quotation row into a breakdown schema."""
        return self._to_breakdown(quotation, is_valid=True)

    def _cart_matches_quotation(
        self, requested: list[tuple[str, int]], quotation: QuotationModel
    ) -> bool:
        current = sorted(requested)
        quoted = sorted((item.product_id, int(item.quantity)) for item in quotation.items)
        return current == quoted and len(quoted) > 0

    def _active_draft(self, sender_id: str, db: Session) -> Optional[QuotationModel]:
        return db.scalar(
            select(QuotationModel)
            .options(selectinload(QuotationModel.items))
            .where(
                QuotationModel.sender_id == sender_id,
                QuotationModel.status == QuotationStatus.DRAFT,
            )
            .order_by(QuotationModel.created_at.desc())
        )

    def _latest_confirmed(self, sender_id: str, db: Session) -> Optional[QuotationModel]:
        return db.scalar(
            select(QuotationModel)
            .options(selectinload(QuotationModel.items))
            .where(
                QuotationModel.sender_id == sender_id,
                QuotationModel.status == QuotationStatus.CONFIRMED,
            )
            .order_by(QuotationModel.confirmed_at.desc(), QuotationModel.id.desc())
        )

    def _upsert_draft(
        self,
        sender_id: str,
        lines: list[QuotationLineBreakdown],
        subtotal: Decimal,
        tax_rate: Decimal,
        tax_amount: Decimal,
        total: Decimal,
        db: Session,
    ) -> str:
        now = datetime.now(timezone.utc)
        draft = self._active_draft(sender_id, db=db)
        if draft is None:
            draft = QuotationModel(
                quotation_id=_new_quotation_id(),
                sender_id=sender_id,
                subtotal=subtotal,
                tax_rate=tax_rate,
                tax=tax_amount,
                total=total,
                status=QuotationStatus.DRAFT,
                enquiry_id=None,
                created_at=now,
                updated_at=now,
            )
            db.add(draft)
            db.flush()
        else:
            draft.subtotal = subtotal
            draft.tax_rate = tax_rate
            draft.tax = tax_amount
            draft.total = total
            draft.status = QuotationStatus.DRAFT
            draft.enquiry_id = None
            draft.updated_at = now
            db.flush()

        self._replace_items(draft, lines, db)
        db.flush()
        return draft.quotation_id

    def _replace_items(
        self, quotation: QuotationModel, lines: list[QuotationLineBreakdown], db: Session
    ) -> None:
        db.execute(
            delete(QuotationItemModel).where(
                QuotationItemModel.quotation_id == quotation.quotation_id
            )
        )
        new_items: list[QuotationItemModel] = []
        for line in lines:
            item = QuotationItemModel(
                quotation_id=quotation.quotation_id,
                product_id=line.product_id,
                product_name=line.name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=line.line_total,
            )
            db.add(item)
            new_items.append(item)
        quotation.items = new_items

    def _to_breakdown(self, quotation: QuotationModel, *, is_valid: bool) -> QuotationBreakdown:
        items = [
            QuotationLineBreakdown(
                product_id=item.product_id,
                name=item.product_name,
                quantity=item.quantity,
                unit_price=money(item.unit_price),
                line_total=money(item.line_total),
            )
            for item in quotation.items
        ]
        # Optional quote-validity window: anchored on confirmation time for
        # confirmed quotations and on creation time for drafts. Informational
        # only — no automatic expiry is enforced (documented in README).
        anchor = quotation.confirmed_at or quotation.created_at
        valid_until: Optional[datetime] = None
        if anchor is not None:
            if anchor.tzinfo is None:
                anchor = anchor.replace(tzinfo=timezone.utc)
            valid_until = anchor + timedelta(days=QUOTE_VALIDITY_DAYS)
        return QuotationBreakdown(
            quotation_id=quotation.quotation_id,
            sender_id=quotation.sender_id,
            status=quotation.status,
            items=items,
            subtotal=money(quotation.subtotal),
            tax_rate=Decimal(str(quotation.tax_rate)),
            tax_amount=money(quotation.tax),
            total=money(quotation.total),
            enquiry_id=quotation.enquiry_id,
            valid_until=valid_until,
            stock_issues=[],
            is_valid=is_valid,
        )


quotation_service = QuotationService()
