class OrderShieldError(Exception):
    """Base class for all business-rule errors."""

    code = "ORDERSHIELD_ERROR"


class ProductNotFound(OrderShieldError):
    code = "PRODUCT_NOT_FOUND"

    def __init__(self):
        super().__init__("Product not found")


class OrderNotFound(OrderShieldError):
    code = "ORDER_NOT_FOUND"

    def __init__(self):
        super().__init__("Order not found")


class InsufficientStock(OrderShieldError):
    code = "INSUFFICIENT_STOCK"

    def __init__(self, available: int):
        super().__init__(f"Insufficient stock. Available: {available}")


class IdempotencyConflict(OrderShieldError):
    code = "IDEMPOTENCY_CONFLICT"

    def __init__(self):
        super().__init__(
            "Idempotency-Key was already used with a different request"
        )


class InvalidTransition(OrderShieldError):
    code = "INVALID_TRANSITION"