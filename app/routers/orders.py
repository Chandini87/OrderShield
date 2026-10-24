from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import OrderNotFound
from app.models import Order
from app.schemas import OrderCreate, OrderOut
from app.services import order_service
from app.services.payment_service import PaymentService, get_payment_service

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post(
    "",
    response_model=OrderOut,
    status_code=201,
    summary="Place an order",
    description=(
        "Reserves stock and processes a simulated payment. "
        "Send a unique `Idempotency-Key` per order; retrying with the same "
        "key returns the original order instead of creating a new one."
    ),
    responses={
        200: {"description": "Key already used: the original order is returned"},
        400: {"description": "Insufficient stock"},
        404: {"description": "Product not found"},
        422: {"description": "Invalid input, or key reused with a different request"},
    },
)

def create_order(
    payload: OrderCreate,
    response: Response,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=100)],
    db: Session = Depends(get_db),
    payment: PaymentService = Depends(get_payment_service),
):
    order, created = order_service.reserve_order(
        db,
        product_id=payload.product_id,
        quantity=payload.quantity,
        idempotency_key=idempotency_key,
    )
    if created:
        order = order_service.process_payment(db, order, payment)
    else:
        response.status_code = 200  # replay of an earlier request
    return order


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise OrderNotFound()
    return order


@router.post(
    "/{order_id}/cancel",
    response_model=OrderOut,
    summary="Cancel an order",
    description="Cancels a confirmed or stock-reserved order and releases its stock.",
    responses={
        404: {"description": "Order not found"},
        409: {"description": "Order cannot be cancelled from its current status"},
    },
)

def cancel_order(order_id: int, db: Session = Depends(get_db)):
    return order_service.cancel_order(db, order_id)