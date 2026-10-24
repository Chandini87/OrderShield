import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.payment_service import get_payment_service


class FakePayment:
    """Test double: set .succeed to control the outcome, .calls counts charges."""

    def __init__(self, succeed: bool = True):
        self.succeed = succeed
        self.calls = 0

    def charge(self, amount: float) -> bool:
        self.calls += 1
        return self.succeed


@pytest.fixture()
def payment():
    return FakePayment()


@pytest.fixture()
def client(payment):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_payment_service] = lambda: payment
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)