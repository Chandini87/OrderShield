import uuid
import logging

def make_product(client, stock=5, price=100):
    return client.post(
        "/products", json={"name": "Phone", "price": price, "stock": stock}
    ).json()


def place_order(client, product_id, quantity=1, key=None):
    return client.post(
        "/orders",
        json={"product_id": product_id, "quantity": quantity},
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )


def stock_of(client, product_id):
    return client.get(f"/products/{product_id}").json()["stock"]


def test_order_success_confirms_and_reduces_stock(client):
    product = make_product(client, stock=5)

    res = place_order(client, product["id"], quantity=2)

    assert res.status_code == 201
    assert res.json()["status"] == "CONFIRMED"
    assert res.json()["total_price"] == 200
    assert stock_of(client, product["id"]) == 3


def test_insufficient_stock_creates_no_order(client):
    product = make_product(client, stock=1)

    res = place_order(client, product["id"], quantity=2)

    assert res.status_code == 400
    assert res.json()["detail"] == "Insufficient stock. Available: 1"
    assert res.json()["code"] == "INSUFFICIENT_STOCK"
    assert stock_of(client, product["id"]) == 1
    assert client.get("/orders/1").status_code == 404


def test_unknown_product(client):
    res = place_order(client, 999)
    assert res.status_code == 404


def test_missing_idempotency_key_rejected(client):
    product = make_product(client)
    res = client.post("/orders", json={"product_id": product["id"], "quantity": 1})
    assert res.status_code == 422


def test_payment_failure_releases_stock(client, payment):
    payment.succeed = False
    product = make_product(client, stock=5)

    res = place_order(client, product["id"], quantity=2)

    assert res.status_code == 201
    assert res.json()["status"] == "PAYMENT_FAILED"
    assert stock_of(client, product["id"]) == 5


def test_duplicate_request_returns_same_order(client, payment):
    product = make_product(client, stock=5)

    first = place_order(client, product["id"], key="abc-123")
    second = place_order(client, product["id"], key="abc-123")

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert stock_of(client, product["id"]) == 4  # reduced once, not twice
    assert payment.calls == 1  # customer charged once


def test_same_key_different_payload_rejected(client):
    product = make_product(client, stock=5)

    place_order(client, product["id"], quantity=1, key="abc-123")
    res = place_order(client, product["id"], quantity=2, key="abc-123")

    assert res.status_code == 422
    assert stock_of(client, product["id"]) == 4


def test_cancel_confirmed_order_releases_stock(client):
    product = make_product(client, stock=5)
    order = place_order(client, product["id"], quantity=2).json()
    assert stock_of(client, product["id"]) == 3

    res = client.post(f"/orders/{order['id']}/cancel")

    assert res.status_code == 200
    assert res.json()["status"] == "CANCELLED"
    assert stock_of(client, product["id"]) == 5


def test_cancel_twice_rejected_and_stock_not_double_released(client):
    product = make_product(client, stock=5)
    order = place_order(client, product["id"], quantity=2).json()

    client.post(f"/orders/{order['id']}/cancel")
    res = client.post(f"/orders/{order['id']}/cancel")

    assert res.status_code == 409
    assert stock_of(client, product["id"]) == 5


def test_cannot_cancel_payment_failed_order(client, payment):
    payment.succeed = False
    product = make_product(client, stock=5)
    order = place_order(client, product["id"]).json()

    res = client.post(f"/orders/{order['id']}/cancel")

    assert res.status_code == 409

def test_order_lifecycle_is_logged(client, caplog):
    caplog.set_level(logging.INFO, logger="ordershield")
    product = make_product(client)

    place_order(client, product["id"], quantity=2)

    events = [record.getMessage() for record in caplog.records]
    assert "stock_reserved" in events
    assert "order_confirmed" in events