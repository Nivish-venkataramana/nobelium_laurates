"""Extracts a compact, semantic snapshot of interactive elements from a
live Playwright page.

This module never returns raw HTML/DOM. It returns plain dicts of the
attributes that matter for identification and future re-location of an
element (role, text, aria-label, test-id, name, placeholder, id, href,
visibility, enabled state).
"""
from __future__ import annotations

from typing import Any

# JS executed inside the page context. Runs once per page and returns a
# JSON-serializable list of interactive element descriptors. Kept
# intentionally narrow (only interactive/labelled elements) to avoid
# flooding the model with noise from a full DOM dump.
_EXTRACTION_SCRIPT = """
() => {
  const SELECTOR = [
    'button', 'a[href]', 'input', 'select', 'textarea',
    '[role="button"]', '[role="link"]', '[role="checkbox"]',
    '[role="radio"]', '[role="tab"]', '[role="menuitem"]',
    '[data-testid]', 'form'
  ].join(',');

  const nodes = Array.from(document.querySelectorAll(SELECTOR));
  const results = [];

  function isVisible(el) {
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
      return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  nodes.forEach((el, idx) => {
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || (tag === 'button' ? 'button' : tag === 'a' ? 'link' : null);
    const text = (el.innerText || el.value || '').trim().slice(0, 200);
    results.push({
      index: idx,
      tag,
      role,
      text: text || null,
      aria_label: el.getAttribute('aria-label'),
      test_id: el.getAttribute('data-testid'),
      name: el.getAttribute('name'),
      placeholder: el.getAttribute('placeholder'),
      element_id_attr: el.getAttribute('id'),
      href: el.getAttribute('href'),
      input_type: el.getAttribute('type'),
      visible: isVisible(el),
      enabled: !el.disabled,
      is_form: tag === 'form',
    });
  });
  return results;
}
"""


async def extract_page_elements(page: Any) -> list[dict]:
    """Run the extraction script against a live Playwright Page object."""
    raw_elements: list[dict] = await page.evaluate(_EXTRACTION_SCRIPT)
    return raw_elements


async def wait_for_stabilization(page: Any, timeout_ms: int = 5000) -> None:
    """Best-effort wait for the page to settle before extraction."""
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        # Some apps (websockets, polling) never go idle; fall back to a
        # short fixed wait rather than failing discovery outright.
        await page.wait_for_timeout(min(timeout_ms, 1500))
