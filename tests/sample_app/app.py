"""
tests/sample_app/app.py
--------------------------
Minimal Flask demo target for AegisQA — proves self-healing and XSS-scanning claims live.

Routes:
    GET  /           → login page
    POST /login      → authenticate (any creds) → redirect to /cart
    GET  /cart       → shopping cart page with "Proceed to Checkout" link
    GET  /checkout   → checkout page (behaviour differs by APP_VERSION)
    POST /checkout   → process order, redirect to /done
    GET  /done       → confirmation page

APP_VERSION toggle (env var or query param):
    v1 (default): <button id="checkout-btn" aria-label="Checkout">Checkout</button>
    v2:           <a role="button" aria-label="Checkout" class="tw-bg-blue-500 tw-btn">
                      Continue to Pay</a>
    Both have accessible role=button, accessible name="Checkout".
    The DOM shape, id, tag, and class all differ — exactly what AegisQA's
    healer must survive on stage.

XSS surface:
    The promo-code field on /checkout echoes the submitted value back into
    the page unescaped (deliberate vulnerability for the security scanner).

Logging:
    Writes Apache-style access logs + Python error tracebacks to
    settings.LOG_WATCH_PATH so monitors/log_watcher.py can tail them.
"""

import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, session, url_for

# ---------------------------------------------------------------------------
# Bootstrap path so we can import config.settings from the project root
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import settings  # noqa: E402

# ---------------------------------------------------------------------------
# Logging setup — writes to LOG_WATCH_PATH
# ---------------------------------------------------------------------------
log_path = Path(settings.LOG_WATCH_PATH)
log_path.parent.mkdir(parents=True, exist_ok=True)

_file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
)
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

log = logging.getLogger("sample_app")
log.setLevel(logging.DEBUG)
log.addHandler(_file_handler)
log.addHandler(_stream_handler)

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = "aegisqa-demo-secret"   # not a real secret — demo only

# ---------------------------------------------------------------------------
# Shared CSS (plain Python string — NOT inside a Jinja2 template to avoid
# conflicts between CSS curly-braces and Jinja2's {{ }} syntax)
# ---------------------------------------------------------------------------
_CSS = """
body { font-family: sans-serif; max-width: 600px; margin: 2rem auto; }
label { display: block; margin: .5rem 0 .2rem; }
input[type=text], input[type=password] { width: 100%; padding: .4rem; box-sizing: border-box; }
button, .tw-btn { padding: .5rem 1.2rem; background: #1d6fcc; color: #fff;
                  border: none; border-radius: 4px; cursor: pointer; display: inline-block; }
.tw-bg-blue-500 { background: #3b82f6; }
nav a { margin-right: 1rem; }
.alert { border: 1px solid #c00; padding: .5rem; margin: .5rem 0; background: #fee; }
.success { border: 1px solid #080; padding: .5rem; margin: .5rem 0; background: #efe; }
.version-badge { float:right; font-size:.75rem; background:#eee; padding:.2rem .5rem; border-radius:4px; }
"""

# ---------------------------------------------------------------------------
# HTML page templates — Jinja2 syntax; CSS is injected via |safe
# ---------------------------------------------------------------------------

_BASE_TMPL = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ title }} — AegisShop</title>
  <style>{{ css | safe }}</style>
</head>
<body>
  <span class="version-badge">APP_VERSION={{ version }}</span>
  <nav><a href="/">Home</a><a href="/cart">Cart</a><a href="/checkout">Checkout</a></nav>
  <hr>
  {{ body | safe }}
</body>
</html>"""

_LOGIN_BODY = """
<h1>Sign In</h1>
{% if error %}<div class="alert">{{ error }}</div>{% endif %}
<form method="POST" action="/login">
  <label for="username">Username</label>
  <input type="text" id="username" name="username"
         aria-label="Username" autocomplete="username" required>

  <label for="password">Password</label>
  <input type="password" id="password" name="password"
         aria-label="Password" autocomplete="current-password" required>
  <br>
  <button type="submit" id="login-btn" aria-label="Sign In">Sign In</button>
</form>
"""

_CART_BODY = """
<h1>Your Cart</h1>
<ul>
  <li>Blue Widget &times; 2 &mdash; $19.99</li>
  <li>Red Gadget &times; 1 &mdash; $49.99</li>
</ul>
<p><strong>Total: $89.97</strong></p>
<a id="checkout-link" href="/checkout"
   role="link" aria-label="Proceed to checkout">
  Proceed to Checkout &rarr;
</a>
"""

# v1 checkout — standard <button> with id="checkout-btn"
_CHECKOUT_V1_BODY = """
<h1>Checkout</h1>
{% if promo_echo %}<div class="alert">Promo applied: {{ promo_echo | safe }}</div>{% endif %}
<form method="POST" action="/checkout" id="checkout-form">
  <label for="card">Card number</label>
  <input type="text" id="card" name="card" aria-label="Card number"
         placeholder="4111 1111 1111 1111">

  <label for="promo">Promo code</label>
  <input type="text" id="promo" name="promo" aria-label="Promo code"
         placeholder="Enter promo code">
  <br>
  <button type="submit" id="checkout-btn" aria-label="Checkout">Checkout</button>
</form>
"""

# v2 checkout — completely different DOM shape; aria-label stays "Checkout"
_CHECKOUT_V2_BODY = """
<h1>Checkout</h1>
{% if promo_echo %}<div class="alert">Promo applied: {{ promo_echo | safe }}</div>{% endif %}
<form method="POST" action="/checkout" id="order-form">
  <label for="promo-v2">Promo code</label>
  <input type="text" id="promo-v2" name="promo" aria-label="Promo code"
         placeholder="Enter promo code">

  <label for="card-v2">Card number</label>
  <input type="text" id="card-v2" name="card" aria-label="Card number"
         placeholder="4111 1111 1111 1111">
  <br>
  <!--
    v2: tag=<a>, no id, different class — SAME aria-label="Checkout" as v1.
    This is the exact mutation AegisQA's healer must survive on stage.
  -->
  <a role="button"
     aria-label="Checkout"
     class="tw-bg-blue-500 tw-btn"
     href="javascript:document.getElementById('order-form').submit()">
    Continue to Pay
  </a>
</form>
"""

_DONE_BODY = """
<h1>Order Confirmed &#10003;</h1>
<div class="success">Thank you! Your order has been placed.</div>
<a href="/">Back to Home</a>
"""


def _get_version() -> str:
    """Resolve APP_VERSION: query param > session > env var > default v1."""
    qp = request.args.get("version")
    if qp in ("v1", "v2"):
        session["app_version"] = qp
    if "app_version" in session:
        return session["app_version"]
    return os.environ.get("APP_VERSION", "v1")


def _render(body_tmpl: str, title: str, **extra_ctx):
    """Render a page: inject body HTML + CSS into the base template."""
    from jinja2 import Environment
    env = Environment(autoescape=False)  # we control escaping manually

    # Render the body template first (handles {% if %} etc.)
    body_html = env.from_string(body_tmpl).render(**extra_ctx)

    # Then render the full page (css and body injected via |safe)
    return render_template_string(
        _BASE_TMPL,
        title=title,
        version=_get_version(),
        css=_CSS,
        body=body_html,
    )


# ── After-request log hook ──────────────────────────────────────────────────
@app.after_request
def _log_request(response):
    log.info(
        '%s [%s] "%s %s" %s',
        request.remote_addr,
        datetime.now(timezone.utc).strftime("%d/%b/%Y:%H:%M:%S +0000"),
        request.method,
        request.full_path,
        response.status_code,
    )
    return response


# ── Error handler — writes a real traceback to the log file ────────────────
@app.errorhandler(Exception)
def _handle_error(exc):
    tb = traceback.format_exc()
    log.error("Unhandled exception:\n%s", tb)
    return f"<h1>500 Internal Server Error</h1><pre>{tb}</pre>", 500


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    """Login page."""
    log.debug("GET /")
    return _render(_LOGIN_BODY, title="Sign In", error=None)


@app.route("/login", methods=["POST"])
def login():
    """Accept any non-empty credentials for the demo."""
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if not username or not password:
        log.warning("Login attempt with empty credentials")
        return _render(_LOGIN_BODY, title="Sign In",
                       error="Username and password are required."), 400
    session["user"] = username
    log.info("User '%s' logged in", username)
    return redirect(url_for("cart"))


@app.route("/cart", methods=["GET"])
def cart():
    """Shopping cart page."""
    log.debug("GET /cart")
    return _render(_CART_BODY, title="Cart")


@app.route("/checkout", methods=["GET"])
def checkout():
    """Checkout page — DOM shape differs between v1 and v2."""
    ver = _get_version()
    promo_echo = request.args.get("promo", "")   # XSS surface — echoed unescaped
    log.debug("GET /checkout  version=%s  promo=%r", ver, promo_echo)
    body_tmpl = _CHECKOUT_V1_BODY if ver == "v1" else _CHECKOUT_V2_BODY
    return _render(body_tmpl, title="Checkout", promo_echo=promo_echo)


@app.route("/checkout", methods=["POST"])
def checkout_post():
    """Process order — redirect back to GET /checkout with promo if supplied."""
    promo = request.form.get("promo", "")
    log.info("Order submitted  promo=%r", promo)
    if promo:
        return redirect(url_for("checkout", promo=promo))
    return redirect(url_for("done"))


@app.route("/done", methods=["GET"])
def done():
    """Order confirmation page."""
    log.debug("GET /done")
    return _render(_DONE_BODY, title="Order Confirmed")


# ---------------------------------------------------------------------------
# Dev-server entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("SAMPLE_APP_PORT", settings.SAMPLE_APP_PORT))
    ver = os.environ.get("APP_VERSION", "v1")
    log.info(
        "Starting AegisShop demo app on http://localhost:%d  (APP_VERSION=%s)", port, ver
    )
    app.run(host="0.0.0.0", port=port, debug=False)
