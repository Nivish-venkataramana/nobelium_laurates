"""The application discovery engine.

URL in -> ApplicationModel out. Uses Playwright to actually load pages;
never fabricates results. Every URL (root and any discovered same-domain
links) is revalidated through validate_target_url before navigation to
prevent SSRF, including via redirects to a different host.
"""
from __future__ import annotations

from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright

from app.core.config import get_settings
from app.core.exceptions import DiscoveryError
from app.core.logging import get_logger
from app.core.security import validate_target_url
from app.schemas.discovery import ApplicationModel
from app.services.discovery.application_model import build_page_model, merge_into_application_model
from app.services.discovery.dom_analyzer import extract_page_elements, wait_for_stabilization

logger = get_logger(__name__)


def _same_domain(url: str, root_netloc: str) -> bool:
    return urlparse(url).netloc == root_netloc


async def discover_application(root_url: str, max_pages: int = 5) -> ApplicationModel:
    """Crawl up to `max_pages` same-domain pages starting from root_url
    and return the merged ApplicationModel.
    """
    settings = get_settings()
    validate_target_url(root_url)

    root_netloc = urlparse(root_url).netloc
    visited: set[str] = set()
    to_visit: list[str] = [root_url]
    page_results = []
    root_title = ""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.BROWSER_HEADLESS)
        try:
            context = await browser.new_context()
            context.set_default_timeout(settings.BROWSER_TIMEOUT_MS)

            while to_visit and len(visited) < max_pages:
                url = to_visit.pop(0)
                if url in visited:
                    continue
                try:
                    validate_target_url(url)
                except Exception as exc:
                    logger.warning("discovery.skip_unsafe_url", url=url, error=str(exc))
                    continue

                page = await context.new_page()
                try:
                    response = await page.goto(url, wait_until="domcontentloaded")
                    # If the server redirected us off-domain, refuse to
                    # extract anything from it (SSRF-via-redirect guard).
                    final_url = page.url
                    if not _same_domain(final_url, root_netloc):
                        logger.warning("discovery.redirect_off_domain", url=url, final_url=final_url)
                        await page.close()
                        continue
                    if response is None or response.status >= 400:
                        logger.warning("discovery.bad_response", url=url, status=getattr(response, "status", None))
                        await page.close()
                        continue

                    await wait_for_stabilization(page, settings.BROWSER_TIMEOUT_MS)
                    title = await page.title()
                    if not root_title:
                        root_title = title

                    raw_elements = await extract_page_elements(page)
                    page_model, elements, forms, navigation, workflows = build_page_model(
                        final_url, title, raw_elements
                    )
                    page_results.append((page_model, elements, forms, navigation, workflows))
                    visited.add(final_url)

                    for nav in navigation:
                        candidate = urljoin(final_url, nav.href)
                        if (
                            _same_domain(candidate, root_netloc)
                            and candidate not in visited
                            and candidate not in to_visit
                            and "#" not in candidate
                        ):
                            to_visit.append(candidate)
                except Exception as exc:  # noqa: BLE001
                    logger.error("discovery.page_error", url=url, error=str(exc))
                finally:
                    await page.close()

            await context.close()
        finally:
            await browser.close()

    if not page_results:
        raise DiscoveryError(f"Could not discover any pages at {root_url}.")

    return merge_into_application_model(root_url, root_title or root_url, page_results)
