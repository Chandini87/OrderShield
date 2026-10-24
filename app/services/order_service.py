from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import (
    IdempotencyConflict,
    InsufficientStock,
    OrderNotFound,
    ProductNotFound,
)
from app.models import Order, OrderStatus, Product
from app.services.payment_service import PaymentService
from app.services.transitions import ensure_can_transition, transition


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
    # 1. Duplicate request? Return the original order.
    existing = _find_by_key(db, idempotency_key)
    if existing:
        _check_same_request(existing, product_id, quantity)
        return existing, False

    product = db.get(Product, product_id)
    if product is None:
        raise ProductNotFound()

    # 2. Insert the order. The UNIQUE constraint on idempotency_key catches
    #    two identical requests that arrive at the same instant.
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
        return existing, False

    # 3. Reserve stock in ONE statement: "subtract only if enough is left".
    #    The check and the update cannot be separated by another request.
    result = db.execute(
        update(Product)
        .where(Product.id == product_id, Product.stock >= quantity)
        .values(stock=Product.stock - quantity)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        db.rollback()  # also removes the order inserted in step 2
        available = db.scalar(select(Product.stock).where(Product.id == product_id))
        raise InsufficientStock(available or 0)

    # 4. Order row + stock change are saved together, or not at all.
    transition(order, OrderStatus.STOCK_RESERVED)
    db.commit()
    return order, True


def process_payment(db: Session, order: Order, payment: PaymentService) -> Order:
    """Charge the customer. On failure, give the reserved stock back."""
    if order.status != OrderStatus.STOCK_RESERVED:
        return order

    try:
        paid = payment.charge(order.total_price)
    except Exception:
        # A real system would ask the gateway what happened. We treat it as failed.
        paid = False

    if paid:
        transition(order, OrderStatus.CONFIRMED)
    else:
        _release_stock(db, order.product_id, order.quantity)
        transition(order, OrderStatus.PAYMENT_FAILED)

    db.commit()  # status change + stock release saved together
    return order


def cancel_order(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise OrderNotFound()

    previous = order.status
    ensure_can_transition(previous, OrderStatus.CANCELLED)

    # Only cancel if the status is still what we just read. If two cancel
    # requests race, exactly one wins, so stock is never released twice.
    result = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == previous)
        .values(status=OrderStatus.CANCELLED)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        db.rollback()
        ensure_can_transition(db.get(Order, order_id).status, OrderStatus.CANCELLED)

    if previous in (OrderStatus.STOCK_RESERVED, OrderStatus.CONFIRMED):
        _release_stock(db, order.product_id, order.quantity)

    db.commit()
    return order