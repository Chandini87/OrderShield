def make_product(client, stock=5):
    return client.post(
        "/products", json={"name": "Phone", "price": 100, "stock": stock}
    ).json()


def test_order_success_reduces_stock(client):
    product = make_product(client, stock=5)

    res = client.post("/orders", json={"product_id": product["id"], "quantity": 2})
    assert res.status_code == 201
    assert res.json()["status"] == "STOCK_RESERVED"
    assert res.json()["total_price"] == 200

    assert client.get(f"/products/{product['id']}").json()["stock"] == 3


def test_insufficient_stock(client):
    product = make_product(client, stock=1)

    res = client.post("/orders", json={"product_id": product["id"], "quantity": 2})
    assert res.status_code == 400
    assert client.get(f"/products/{product['id']}").json()["stock"] == 1


def test_unknown_product(client):
    res = client.post("/orders", json={"product_id": 999, "quantity": 1})
    assert res.status_code == 404