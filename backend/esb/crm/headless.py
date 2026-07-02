"""Shared headless-browser rendering (Playwright/Chromium) for JS-built pages
that return an empty shell to a plain HTTP fetch — state report-card
dashboards, modern district sites, etc.

Degrades gracefully to a no-op if Playwright/Chromium isn't available in
the runtime. See RESEARCH_PLAN.md §1.5 for the politeness/anti-blocking
scope this stays within (honest UA, no proxy rotation, no CAPTCHA-solving).
"""
from __future__ import annotations

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def render_html(url: str, wait_ms: int = 1800, timeout_ms: int = 20000) -> str | None:
    """Render a JS-built page with headless Chromium. Returns the post-JS
    HTML, or None if Playwright is unavailable or the page fails."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(user_agent=BROWSER_UA)
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            html = page.content()
            browser.close()
            return html
    except Exception:
        return None
