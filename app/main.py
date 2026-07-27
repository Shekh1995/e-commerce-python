import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request
from werkzeug.security import check_password_hash, generate_password_hash


def create_app(test_config=None):
    app = Flask(__name__)

    @app.route("/")
    def home() :
        return render_template ("index.html")
    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=8081)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE_PATH", str(Path(app.instance_path) / "store.db")),
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    def connection():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db():
        db = connection()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL, token TEXT UNIQUE
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT,
                price_cents INTEGER NOT NULL CHECK(price_cents >= 0), stock INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS cart_items (
                user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL CHECK(quantity > 0),
                PRIMARY KEY(user_id, product_id), FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, total_cents INTEGER NOT NULL,
                created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS order_items (
                order_id INTEGER NOT NULL, product_id INTEGER NOT NULL, product_name TEXT NOT NULL,
                unit_price_cents INTEGER NOT NULL, quantity INTEGER NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(id)
            );
            """
        )
        product_count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if product_count == 0:
            db.executemany(
                "INSERT INTO products(name, description, price_cents, stock) VALUES (?, ?, ?, ?)",
                [
                    ("Wireless Headphones", "Comfortable over-ear headphones with clear sound.", 4999, 18),
                    ("Smart Watch", "Track your activity, notifications, and daily goals.", 7999, 12),
                    ("Laptop Backpack", "Water-resistant backpack with a padded laptop sleeve.", 3599, 24),
                    ("Portable Speaker", "Compact wireless speaker with rich, room-filling sound.", 2999, 20),
                ],
            )
        db.commit()

    def error(message, status=400):
        return jsonify({"error": message}), status

    def current_user():
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None
        return connection().execute(
            "SELECT id, email FROM users WHERE token = ?", (header[7:],)
        ).fetchone()

    def require_user():
        user = current_user()
        if user is None:
            return None, error("authentication required", 401)
        return user, None

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/")
    def storefront():
        return render_template("index.html")

    @app.post("/auth/register")
    def register():
        data = request.get_json(silent=True) or {}
        email, password = data.get("email", ""), data.get("password", "")
        if not email or len(password) < 8:
            return error("email and an 8-character password are required")
        try:
            connection().execute(
                "INSERT INTO users(email, password_hash) VALUES (?, ?)",
                (email.lower(), generate_password_hash(password)),
            )
            connection().commit()
        except sqlite3.IntegrityError:
            return error("email is already registered", 409)
        return jsonify({"email": email.lower()}), 201

    @app.post("/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        user = connection().execute(
            "SELECT * FROM users WHERE email = ?", (data.get("email", "").lower(),)
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], data.get("password", "")):
            return error("invalid email or password", 401)
        token = secrets.token_urlsafe(32)
        connection().execute("UPDATE users SET token = ? WHERE id = ?", (token, user["id"]))
        connection().commit()
        return {"token": token}

    @app.get("/products")
    def products():
        rows = connection().execute("SELECT * FROM products ORDER BY id").fetchall()
        return jsonify([dict(row) for row in rows])

    @app.post("/products")
    def add_product():
        data = request.get_json(silent=True) or {}
        try:
            name = data["name"].strip()
            price_cents, stock = int(data["price_cents"]), int(data.get("stock", 0))
            if not name or price_cents < 0 or stock < 0:
                raise ValueError
        except (KeyError, AttributeError, TypeError, ValueError):
            return error("name, non-negative price_cents, and non-negative stock are required")
        cursor = connection().execute(
            "INSERT INTO products(name, description, price_cents, stock) VALUES (?, ?, ?, ?)",
            (name, data.get("description", ""), price_cents, stock),
        )
        connection().commit()
        return jsonify({"id": cursor.lastrowid, "name": name}), 201

    @app.get("/cart")
    def get_cart():
        user, response = require_user()
        if response:
            return response
        rows = connection().execute(
            """SELECT p.id, p.name, p.price_cents, c.quantity, (p.price_cents * c.quantity) AS subtotal_cents
               FROM cart_items c JOIN products p ON p.id = c.product_id WHERE c.user_id = ?""", (user["id"],)
        ).fetchall()
        items = [dict(row) for row in rows]
        return {"items": items, "total_cents": sum(item["subtotal_cents"] for item in items)}

    @app.put("/cart/<int:product_id>")
    def update_cart(product_id):
        user, response = require_user()
        if response:
            return response
        quantity = (request.get_json(silent=True) or {}).get("quantity")
        if not isinstance(quantity, int) or quantity < 1:
            return error("quantity must be a positive integer")
        product = connection().execute("SELECT stock FROM products WHERE id = ?", (product_id,)).fetchone()
        if product is None:
            return error("product not found", 404)
        if quantity > product["stock"]:
            return error("requested quantity exceeds stock", 409)
        connection().execute(
            "INSERT INTO cart_items(user_id, product_id, quantity) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = excluded.quantity",
            (user["id"], product_id, quantity),
        )
        connection().commit()
        return {"product_id": product_id, "quantity": quantity}

    @app.post("/orders/checkout")
    def checkout():
        user, response = require_user()
        if response:
            return response
        db = connection()
        items = db.execute(
            """SELECT p.id, p.name, p.price_cents, p.stock, c.quantity FROM cart_items c
               JOIN products p ON p.id = c.product_id WHERE c.user_id = ?""", (user["id"],)
        ).fetchall()
        if not items:
            return error("cart is empty", 409)
        if any(item["quantity"] > item["stock"] for item in items):
            return error("one or more items are out of stock", 409)
        total = sum(item["price_cents"] * item["quantity"] for item in items)
        cursor = db.execute(
            "INSERT INTO orders(user_id, total_cents, created_at) VALUES (?, ?, ?)",
            (user["id"], total, datetime.now(timezone.utc).isoformat()),
        )
        order_id = cursor.lastrowid
        for item in items:
            db.execute(
                "INSERT INTO order_items VALUES (?, ?, ?, ?, ?)",
                (order_id, item["id"], item["name"], item["price_cents"], item["quantity"]),
            )
            db.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (item["quantity"], item["id"]))
        db.execute("DELETE FROM cart_items WHERE user_id = ?", (user["id"],))
        db.commit()
        return {"order_id": order_id, "total_cents": total}, 201

    with app.app_context():
        init_db()
    return app


app = create_app()
