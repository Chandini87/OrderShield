import os
import random


class PaymentService:
    """Simulated payment gateway. Fails randomly at `failure_rate`."""

    def __init__(self, failure_rate: float = 0.2):
        self.failure_rate = failure_rate

    def charge(self, amount: float) -> bool:
        return random.random() >= self.failure_rate


def get_payment_service() -> PaymentService:
    rate = float(os.getenv("PAYMENT_FAILURE_RATE", "0.2"))
    return PaymentService(failure_rate=rate)