import pytest

from app.exceptions import InvalidTransition
from app.models import OrderStatus
from app.services.transitions import ensure_can_transition


def test_valid_transition_allowed():
    ensure_can_transition(OrderStatus.PENDING, OrderStatus.STOCK_RESERVED)


@pytest.mark.parametrize(
    "current,new",
    [
        (OrderStatus.CONFIRMED, OrderStatus.PENDING),
        (OrderStatus.CANCELLED, OrderStatus.CONFIRMED),
        (OrderStatus.PAYMENT_FAILED, OrderStatus.CONFIRMED),
        (OrderStatus.PENDING, OrderStatus.CONFIRMED),
    ],
)
def test_invalid_transitions_rejected(current, new):
    with pytest.raises(InvalidTransition):
        ensure_can_transition(current, new)