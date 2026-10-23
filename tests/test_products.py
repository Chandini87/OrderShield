def test_create_and_list_products(client):
    res = client.post("/products", json={"name": "Phone", "price": 15000, "stock": 5})
    assert res.status_code == 201
    assert res.json()["stock"] == 5

    res = client.get("/products")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_invalid_product_rejected(client):
    res = client.post("/products", json={"name": "Phone", "price": -1, "stock": 5})
    assert res.status_code == 422