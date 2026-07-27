from app.main import create_app


def test_checkout_reduces_stock(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})
    client = app.test_client()
    assert client.post("/auth/register", json={"email": "a@example.com", "password": "password1"}).status_code == 201
    token = client.post("/auth/login", json={"email": "a@example.com", "password": "password1"}).get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    product = client.post("/products", json={"name": "Notebook", "price_cents": 500, "stock": 3}).get_json()
    assert client.put(f"/cart/{product['id']}", json={"quantity": 2}, headers=headers).status_code == 200
    order = client.post("/orders/checkout", headers=headers)
    assert order.status_code == 201
    assert order.get_json()["total_cents"] == 1000
