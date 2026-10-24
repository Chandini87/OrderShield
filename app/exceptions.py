class OrderShieldError(Exception):
    """Base class for all business-rule errors."""


class ProductNotFound(OrderShieldError):
    def __init__(self):
        super().__init__("Product not found")


class OrderNotFound(OrderShieldError):
    def __init__(self):
        super().__init__("Order not found")


class InsufficientStock(OrderShieldError):
    def __init__(self, available: int):
        super().__init__(f"Insufficient stock. Available: {available}")


class IdempotencyConflict(OrderShieldError):
    def __init__(self):
        super().__init__(
            "Idempotency-Key was already used with a different request"
        )


class InvalidTransition(OrderShieldError):
    pass