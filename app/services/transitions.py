from app.exceptions import InvalidTransition
from app.models import Order, OrderStatus

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.STOCK_RESERVED, OrderStatus.CANCELLED},
    OrderStatus.STOCK_RESERVED: {
        OrderStatus.CONFIRMED,
        OrderStatus.PAYMENT_FAILED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.CONFIRMED: {OrderStatus.CANCELLED},
    OrderStatus.PAYMENT_FAILED: set(),  # final
    OrderStatus.CANCELLED: set(),       # final
}


def ensure_can_transition(current: OrderStatus, new: OrderStatus) -> None:
    if new not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(
            f"Cannot change order status from {current.value} to {new.value}"
        )


def transition(order: Order, new: OrderStatus) -> None:
    ensure_can_transition(order.status, new)
    order.status = new