import threading
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.exceptions import InsufficientStock
from app.models import Order, Product
from app.services import order_service


def make_session_factory(tmp_path):
    db_file = (tmp_path / "race.db").as_posix()
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def run_in_threads(count, target):
    barrier = threading.Barrier(count)  # make all threads start together

    def runner():
        barrier.wait()
        target()

    threads = [threading.Thread(target=runner) for _ in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def test_only_one_buyer_gets_the_last_item(tmp_path):
    Session = make_session_factory(tmp_path)
    with Session() as db:
        db.add(Product(name="Phone", price=100, stock=1))
        db.commit()

    results = []

    def buy():
        db = Session()
        try:
            order_service.reserve_order(
                db, product_id=1, quantity=1, idempotency_key=str(uuid.uuid4())
            )
            results.append("bought")
        except InsufficientStock:
            results.append("sold_out")
        finally:
            db.close()

    run_in_threads(10, buy)

    assert results.count("bought") == 1
    assert results.count("sold_out") == 9
    with Session() as db:
        assert db.get(Product, 1).stock == 0
        assert len(db.scalars(select(Order)).all()) == 1


def test_same_key_sent_concurrently_creates_one_order(tmp_path):
    Session = make_session_factory(tmp_path)
    with Session() as db:
        db.add(Product(name="Phone", price=100, stock=10))
        db.commit()

    created_flags = []

    def buy():
        db = Session()
        try:
            _, created = order_service.reserve_order(
                db, product_id=1, quantity=1, idempotency_key="double-click"
            )
            created_flags.append(created)
        finally:
            db.close()

    run_in_threads(10, buy)

    assert len(created_flags) == 10
    assert created_flags.count(True) == 1
    with Session() as db:
        assert db.get(Product, 1).stock == 9
        assert len(db.scalars(select(Order)).all()) == 1