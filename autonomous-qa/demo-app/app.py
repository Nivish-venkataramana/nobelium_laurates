"""A small, genuinely functional demo web application used to exercise
the Autonomous QA Platform end to end.

LOGIN_LABEL controls whether the login button reads "Login" (version A)
or "Sign In" (version B). This is the ONLY toggle used to demonstrate
self-healing — the QA platform itself contains no special-cased logic
for this app; it discovers and heals the relabeled control the same way
it would for any other application.
"""
from __future__ import annotations

import os

from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("DEMO_APP_SECRET", "demo-secret-key-not-for-production")

LOGIN_LABEL = os.environ.get("LOGIN_LABEL", "Login")  # "Login" or "Sign In"
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"

PRODUCTS = [
    {"id": 1, "name": "Wireless Mouse", "price": 24.99},
    {"id": 2, "name": "Mechanical Keyboard", "price": 89.99},
    {"id": 3, "name": "USB-C Hub", "price": 39.99},
    {"id": 4, "name": "Laptop Stand", "price": 34.5},
]

USERS = {"demo@example.com": "password123"}


@app.route("/")
def home():
    return render_template("home.html", login_label=LOGIN_LABEL)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        if USERS.get(email) == password:
            session["user"] = email
            return redirect(url_for("dashboard"))
        error = "Invalid email or password."
    return render_template("login.html", login_label=LOGIN_LABEL, error=error)


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=session["user"], login_label=LOGIN_LABEL)


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))


@app.route("/register", methods=["GET", "POST"])
def register():
    message = None
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        if not email or not password:
            message = "Email and password are required."
        elif email in USERS:
            message = "An account with that email already exists."
        else:
            USERS[email] = password
            message = "Account created successfully. You can now sign in."
    return render_template("register.html", login_label=LOGIN_LABEL, message=message)


@app.route("/products")
def products():
    return render_template("products.html", products=PRODUCTS, login_label=LOGIN_LABEL)


@app.route("/cart/add/<int:product_id>")
def add_to_cart(product_id: int):
    cart = session.get("cart", [])
    cart.append(product_id)
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart")
def cart():
    cart_ids = session.get("cart", [])
    items = [p for p in PRODUCTS if p["id"] in cart_ids]
    total = sum(p["price"] for p in items)
    return render_template("cart.html", items=items, total=total, login_label=LOGIN_LABEL)


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if request.method == "POST":
        session["cart"] = []
        return render_template("confirmation.html", login_label=LOGIN_LABEL)
    cart_ids = session.get("cart", [])
    items = [p for p in PRODUCTS if p["id"] in cart_ids]
    total = sum(p["price"] for p in items)
    return render_template("checkout.html", items=items, total=total, login_label=LOGIN_LABEL)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    sent = False
    if request.method == "POST":
        sent = True
    return render_template("contact.html", sent=sent, login_label=LOGIN_LABEL)


@app.route("/debug/set-login-label", methods=["POST"])
def set_login_label():
    """Test-harness-only endpoint: lets an automated E2E test flip this
    demo app's own login button label at runtime, so a single test
    session can exercise both versions without restarting the process.
    Guarded by DEMO_MODE so it can never be reachable in a normal
    deployment. This mutates the SUT for test purposes only — it has no
    effect on, and is not used by, the QA platform's healing engine,
    which must independently rediscover the change either way."""
    global LOGIN_LABEL
    if not DEMO_MODE:
        return {"error": "Not available outside DEMO_MODE."}, 403
    label = request.json.get("label") if request.is_json else None
    if label not in ("Login", "Sign In"):
        return {"error": "label must be 'Login' or 'Sign In'."}, 400
    LOGIN_LABEL = label
    return {"login_label": LOGIN_LABEL}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)), debug=False)
