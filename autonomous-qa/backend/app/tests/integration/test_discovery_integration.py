"""Integration test: runs real Playwright discovery against the bundled
demo-app. Skipped automatically if the demo app isn't reachable (e.g. in
a CI job that doesn't start the docker-compose stack) or Playwright's
browser binary isn't installed.

Run with the full stack up:
    docker compose up -d demo-app
    pytest app/tests/integration/test_discovery_integration.py
"""
from __future__ import annotations

import os

import pytest

DEMO_APP_URL = os.environ.get("DEMO_APP_URL", "http://localhost:5050")


def _demo_app_reachable() -> bool:
    import urllib.request

    try:
        urllib.request.urlopen(DEMO_APP_URL, timeout=2)
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.asyncio
@pytest.mark.skipif(not _demo_app_reachable(), reason="demo-app is not running/reachable")
async def test_discovery_finds_login_page_and_elements():
    from app.services.discovery.crawler import discover_application

    model = await discover_application(DEMO_APP_URL, max_pages=5)

    urls = {p.url for p in model.pages}
    assert any("login" in u for u in urls)

    login_page_elements = [e for e in model.elements if "login" in e.page_url]
    assert len(login_page_elements) > 0
