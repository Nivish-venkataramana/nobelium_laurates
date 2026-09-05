"""
core/crawler.py
----------------
Discovers an application's routes, forms, and interactive elements by
driving Playwright headless Chromium and extracting the accessibility (a11y)
tree — never relying on DOM structure or class names.

Public API:
    crawler = Crawler()
    graph   = crawler.crawl(base_url, max_depth, max_pages)  -> CrawlGraph dict

CrawlGraph shape is documented in docs/SCHEMAS.md.

NOTE: Uses page.aria_snapshot() (Playwright >=1.47) and get_by_role().all()
instead of the removed page.accessibility.snapshot().
"""

import logging
from collections import deque
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, sync_playwright

from config.settings import settings

log = logging.getLogger(__name__)

# ARIA roles to collect as interactive elements
_INTERACTIVE_ROLES = [
    "button", "link", "textbox", "checkbox", "radio", "combobox",
    "listbox", "menuitem", "searchbox", "spinbutton", "switch", "tab",
]


class Crawler:
    """
    BFS accessibility-tree crawler.

    Usage::

        graph = Crawler().crawl("http://localhost:5000", max_depth=3, max_pages=25)
    """

    def crawl(
        self,
        base_url: str,
        max_depth: int | None = None,
        max_pages: int | None = None,
    ) -> dict:
        """
        Crawl *base_url* up to *max_depth* link-hops and *max_pages* pages.

        Returns a CrawlGraph dict (JSON-serialisable) matching docs/SCHEMAS.md.
        """
        max_depth = max_depth if max_depth is not None else settings.CRAWLER_MAX_DEPTH
        max_pages = max_pages if max_pages is not None else settings.CRAWLER_MAX_PAGES

        parsed_base = urlparse(base_url)
        origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

        pages_data: list[dict] = []
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(base_url, 0)])

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 900},
                ignore_https_errors=True,
            )
            page = ctx.new_page()

            try:
                while queue and len(pages_data) < max_pages:
                    url, depth = queue.popleft()
                    norm = self._normalise(url)
                    if norm in visited:
                        continue
                    visited.add(norm)

                    log.info("Crawling [depth=%d] %s", depth, norm)
                    data = self._visit(page, norm)
                    if data:
                        pages_data.append(data)
                        if depth < max_depth:
                            for link in data.get("links", []):
                                abs_link = urljoin(norm, link)
                                if abs_link.startswith(origin):
                                    norm_link = self._normalise(abs_link)
                                    if norm_link not in visited:
                                        queue.append((norm_link, depth + 1))
            finally:
                ctx.close()
                browser.close()

        graph = {"base_url": base_url, "pages": pages_data}
        log.info("Crawl complete: %d pages from %s", len(pages_data), base_url)
        return graph

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(url: str) -> str:
        p = urlparse(url)
        return p._replace(fragment="").geturl().rstrip("?")

    def _visit(self, page: Page, url: str) -> dict | None:
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=12_000)
            if resp and resp.status >= 400:
                log.warning("HTTP %d for %s — skipping", resp.status, url)
                return None
        except Exception as exc:
            log.warning("Navigation error for %s: %s", url, exc)
            return None

        title = page.title()

        # ── ARIA snapshot (Playwright >= 1.47) ───────────────────────────
        try:
            a11y_snapshot = page.aria_snapshot()
        except Exception as exc:
            log.debug("aria_snapshot failed for %s: %s", url, exc)
            a11y_snapshot = ""

        # ── Interactive elements via get_by_role ─────────────────────────
        interactive = self._collect_interactive(page)

        # ── Forms ────────────────────────────────────────────────────────
        forms = self._extract_forms(page)

        # ── Same-origin links ────────────────────────────────────────────
        links = self._extract_links(page)

        parsed = urlparse(url)
        rel_url = parsed.path + (("?" + parsed.query) if parsed.query else "")

        return {
            "url": rel_url or "/",
            "title": title,
            "a11y_snapshot": a11y_snapshot,   # str (YAML-like aria snapshot)
            "interactive_elements": interactive,
            "forms": forms,
            "links": links,
        }

    @staticmethod
    def _collect_interactive(page: Page) -> list[dict]:
        """Enumerate interactive elements by querying each ARIA role."""
        results: list[dict] = []
        seen: set[tuple] = set()

        for role in _INTERACTIVE_ROLES:
            try:
                locators = page.get_by_role(role).all()  # type: ignore[arg-type]
            except Exception:
                continue

            for loc in locators:
                try:
                    # Get the accessible name via inner_text or aria-label
                    name = ""
                    try:
                        name = (
                            loc.get_attribute("aria-label")
                            or loc.get_attribute("aria-labelledby")
                            or loc.inner_text()
                            or ""
                        ).strip()[:120]
                    except Exception:
                        pass

                    key = (role, name)
                    if key in seen or not name:
                        continue
                    seen.add(key)

                    # Bounding box
                    try:
                        bb = loc.bounding_box() or {"x": 0, "y": 0, "width": 0, "height": 0}
                    except Exception:
                        bb = {"x": 0, "y": 0, "width": 0, "height": 0}

                    selector_hint = f'role={role}[name="{name}"]'
                    results.append({
                        "role": role,
                        "accessible_name": name,
                        "selector_hint": selector_hint,
                        "bounding_box": bb,
                    })
                except Exception:
                    continue

        return results

    @staticmethod
    def _extract_forms(page: Page) -> list[dict]:
        try:
            return page.evaluate("""() => {
                return Array.from(document.querySelectorAll('form')).map(form => {
                    const fields = Array.from(
                        form.querySelectorAll('input, textarea, select')
                    ).map(el => ({
                        role: el.tagName.toLowerCase() === 'select' ? 'combobox' :
                              el.type === 'checkbox' ? 'checkbox' :
                              el.type === 'radio'    ? 'radio'    : 'textbox',
                        accessible_name:
                            el.labels && el.labels[0] ? el.labels[0].textContent.trim()
                            : (el.getAttribute('aria-label') || el.placeholder || el.name || ''),
                        input_type: el.type || el.tagName.toLowerCase()
                    }));
                    return { form_id: form.id || form.name || null, fields };
                });
            }""")
        except Exception as exc:
            log.debug("Form extraction failed: %s", exc)
            return []

    @staticmethod
    def _extract_links(page: Page) -> list[str]:
        try:
            return page.evaluate("""() => [...new Set(
                Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.getAttribute('href'))
                    .filter(h => h && !h.startsWith('javascript:')
                                   && !h.startsWith('mailto:')
                                   && !h.startsWith('#'))
            )]""")
        except Exception as exc:
            log.debug("Link extraction failed: %s", exc)
            return []
