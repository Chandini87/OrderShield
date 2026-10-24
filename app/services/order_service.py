import logging

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import (
    IdempotencyConflict,
    InsufficientStock,
    OrderNotFound,
    ProductNotFound,
)
from app.logging_config import log_event
from app.models import Order, OrderStatus, Product
from app.services.payment_service import PaymentService
from app.services.transitions import ensure_can_transition, transition

logger = logging.getLogger("ordershield.orders")


def _find_by_key(db: Session, key: str) -> Order | None:
    return db.scalar(select(Order).where(Order.idempotency_key == key))


def _check_same_request(order: Order, product_id: int, quantity: int) -> None:
    if order.product_id != product_id or order.quantity != quantity:
        raise IdempotencyConflict()


def _release_stock(db: Session, product_id: int, quantity: int) -> None:
    db.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(stock=Product.stock + quantity)
        .execution_options(synchronize_session=False)
    )


def reserve_order(
    db: Session, *, product_id: int, quantity: int, idempotency_key: str
) -> tuple[Order, bool]:
    """Create an order and reserve stock.

    Returns (order, created). created=False means this idempotency key
    was already used, so the existing order is returned unchanged.
    """
    existing = _find_by_key(db, idempotency_key)
    if existing:
        _check_same_request(existing, product_id, quantity)
        log_event(
            logger, "duplicate_request_ignored",
            order_id=existing.id, idempotency_key=idempotency_key,
        )
        return existing, False

    product = db.get(Product, product_id)
    if product is None:
        raise ProductNotFound()

    order = Order(
        idempotency_key=idempotency_key,
        product_id=product_id,
        quantity=quantity,
        total_price=product.price * quantity,
        status=OrderStatus.PENDING,
    )
    db.add(order)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = _find_by_key(db, idempotency_key)
        if existing is None:
            raise
        _check_same_request(existing, product_id, quantity)
        log_event(
            logger, "duplicate_request_ignored",
            order_id=existing.id, idempotency_key=idempotency_key,
        )
        return existing, False

    result = db.execute(
        update(Product)
        .where(Product.id == product_id, Product.stock >= quantity)
        .values(stock=Product.stock - quantity)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        db.rollback()
        available = db.scalar(select(Product.stock).where(Product.id == product_id)) or 0
        log_event(
            logger, "insufficient_stock", level=logging.WARNING,
            product_id=product_id, requested=quantity, available=available,
        )
        raise InsufficientStock(available)

    transition(order, OrderStatus.STOCK_RESERVED)
    order_id = order.id
    db.commit()
    log_event(
        logger, "stock_reserved",
        order_id=order_id, product_id=product_id, quantity=quantity,
    )
    return order, True


def process_payment(db: Session, order: Order, payment: PaymentService) -> Order:
    """Charge the customer. On failure, give the reserved stock back."""
    if order.status != OrderStatus.STOCK_RESERVED:
        return order

    order_id, product_id = order.id, order.product_id
    quantity, total = order.quantity, order.total_price

    try:
        paid = payment.charge(total)
    except Exception as exc:
        log_event(
            logger, "payment_gateway_error", level=logging.ERROR,
            order_id=order_id, error=str(exc),
        )
        paid = False

    if paid:
        transition(order, OrderStatus.CONFIRMED)
        db.commit()
        log_event(logger, "order_confirmed", order_id=order_id, total_price=total)
    else:
        _release_stock(db, product_id, quantity)
        transition(order, OrderStatus.PAYMENT_FAILED)
        db.commit()
        log_event(logger, "payment_failed", level=logging.WARNING, order_id=order_id)
        log_event(
            logger, "stock_released",
            order_id=order_id, product_id=product_id, quantity=quantity,
        )
    return order


def cancel_order(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise OrderNotFound()

    previous = order.status
    product_id, quantity = order.product_id, order.quantity
    ensure_can_transition(previous, OrderStatus.CANCELLED)

    result = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == previous)
        .values(status=OrderStatus.CANCELLED)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        db.rollback()
        ensure_can_transition(db.get(Order, order_id).status, OrderStatus.CANCELLED)

    released = previous in (OrderStatus.STOCK_RESERVED, OrderStatus.CONFIRMED)
    if released:
        _release_stock(db, product_id, quantity)

    db.commit()
    log_event(
        logger, "order_cancelled",
        order_id=order_id, previous_status=previous.value,
    )
    if released:
        log_event(
            logger, "stock_released",
            order_id=order_id, product_id=product_id, quantity=quantity,
        )
    return order