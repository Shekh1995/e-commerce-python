# Python E-commerce API

A compact Flask and SQLite e-commerce API with user registration/login, a product catalog, carts, stock checks, and checkout.

## Run locally

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/flask --app app.main run --port 3000
```

## Main endpoints

- `POST /auth/register`
- `POST /auth/login`
- `GET` and `POST /products`
- `GET /cart`, `PUT /cart/{product_id}`
- `POST /orders/checkout`

Use the token returned by login as `Authorization: Bearer <token>` for cart and checkout routes.
