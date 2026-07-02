"""Polite crawler that finds a district's board/leadership pages and harvests
official-domain emails. Respects robots.txt and rate-limits per host.

Ported from coach-devon's verifier/crawl.py. Headless Chromium (Playwright)
renders JS-built pages that a plain HTTP fetch would return as an empty
shell — this degrades gracefully to a no-op if Playwright/Chromium isn't
available in the runtime, same behavior the source has when Playwright
is absent.
"""
from __future__ import annotations

import time
import urllib.parse
import urllib.robotparser

import httpx

from esb.core.config import settings
from esb.crm.headless import render_html as _render_html
from esb.crm.verifier.extract import emails_from_html

UA = "ESBPortalBot/0.1 (+ESB school-board outreach; contact aj@effectiveschoolboards.com)"


BOARD_HINTS = ("board", "leadership", "administration", "superintendent",
               "our-district", "board-of-education", "boe", "trustees", "directory")

COMMON_BOARD_PATHS = (
    "/school-board", "/board", "/board-of-education", "/our-district/school-board",
    "/district/board-of-education", "/about/school-board", "/board-of-trustees",
    "/our-board", "/leadership", "/administration", "/staff-directory", "/directory",
    "/superintendent", "/our-superintendent", "/about/superintendent",
    "/district/superintendent", "/administration/superintendent", "/superintendents-office",
)

CMS_SIGNATURES = {
    "finalsite": ("finalsite", "fsboardmember", "/fs/", "data-fs-"),
    "apptegy": ("apptegy", "thrillshare", "cdn.thrillshare"),
    "blackboard": ("schoolwires", "blackboard", "/site/default.aspx", "cmsid", "ui-widget"),
    "edlio": ("edlio", "edl.io"),
    "squarespace": ("squarespace", "static1.squarespace"),
    "wordpress": ("/wp-content/", "/wp-json/", "wp-includes"),
    "googlesites": ("sites.google.com", "gstatic.com/sites"),
    "foxbright": ("foxbright",),
    "catapult": ("catapultcms", "cms4schools", "schoolpointe"),
    "campussuite": ("campussuite", "campus suite"),
}
CMS_BOARD_PATHS = {
    "finalsite": ("/about/board-of-education", "/board-of-education", "/apps/pages/board",
                  "/our-district/board-of-education", "/district/school-board"),
    "apptegy": ("/page/school-board", "/page/board-of-education", "/page/board-of-trustees",
                "/page/our-board", "/page/board"),
    "blackboard": ("/domain/13", "/domain/8", "/domain/4", "/Page/board-of-education", "/site/Default.aspx?PageID=1"),
    "edlio": ("/apps/pages/board", "/board", "/our-board"),
    "wordpress": ("/school-board", "/board-of-education", "/our-board", "/board"),
    "squarespace": ("/board", "/school-board", "/board-of-education"),
    "googlesites": ("/board", "/school-board"),
    "foxbright": ("/Board-of-Education", "/board"),
    "catapult": ("/Board-of-Education", "/board-of-education"),
    "campussuite": ("/board-of-education", "/school-board"),
}


def detect_cms(html: str) -> str:
    low = html.lower()
    for plat, sigs in CMS_SIGNATURES.items():
        if any(s in low for s in sigs):
            return plat
    return ""


_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}
_last_hit: dict[str, float] = {}
MIN_INTERVAL = 1.5


def _host(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower()


def normalize_url(website: str) -> str:
    website = website.strip()
    if not website:
        return ""
    if not website.startswith(("http://", "https://")):
        website = "http://" + website
    return website


def domain_from_url(url: str) -> str:
    host = _host(url)
    return host[4:] if host.startswith("www.") else host


def _allowed(url: str) -> bool:
    if not settings.respect_robots:
        return True
    host = _host(url)
    rp = _robots_cache.get(host)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = httpx.get(f"https://{host}/robots.txt", timeout=8, follow_redirects=True,
                          headers={"User-Agent": UA})
            if r.status_code == 200 and "text" in r.headers.get("content-type", "") \
                    and "Disallow" in r.text:
                rp.parse(r.text.splitlines())
            else:
                rp.parse([])
        except Exception:
            rp.parse([])
        _robots_cache[host] = rp
    try:
        return rp.can_fetch(UA, url)
    except Exception:
        return True


def _throttle(url: str) -> None:
    host = _host(url)
    wait = MIN_INTERVAL - (time.monotonic() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()


def _fetch(client: httpx.Client, url: str) -> str | None:
    if not _allowed(url):
        return None
    _throttle(url)
    try:
        r = client.get(url, timeout=15, follow_redirects=True)
        if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
            return r.text
    except Exception:
        return None
    return None


def discover_emails(website: str, max_pages: int = 9, render: bool = False) -> dict:
    """Crawl a district site for board/leadership emails on its own domain.
    Returns {domain, emails: [...], pages_crawled, board_pages: [...]}."""
    start = normalize_url(website)
    if not start:
        return {"domain": "", "emails": [], "pages_crawled": 0, "board_pages": []}
    domain = domain_from_url(start)
    emails: set[str] = set()
    board_pages: list[str] = []
    crawled = 0

    with httpx.Client(headers={"User-Agent": UA}) as client:
        home = _fetch(client, start)
        crawled += 1
        if not home:
            return {"domain": domain, "emails": [], "pages_crawled": crawled,
                    "board_pages": [], "board_text": "", "platform": ""}
        emails |= emails_from_html(home, domain)

        platform = detect_cms(home)

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(home, "html.parser")
        candidates: list[str] = []
        for p in CMS_BOARD_PATHS.get(platform, ()):
            candidates.append(urllib.parse.urljoin(start, p))
        for a in soup.find_all("a", href=True):
            href, text = a["href"], (a.get_text() or "").lower()
            blob = (href + " " + text).lower()
            if any(h in blob for h in BOARD_HINTS):
                full = urllib.parse.urljoin(start, href)
                if domain in _host(full) and full not in candidates:
                    candidates.append(full)

        for p in COMMON_BOARD_PATHS:
            u = urllib.parse.urljoin(start, p)
            if u not in candidates:
                candidates.append(u)

        texts: list[str] = []
        for url in candidates[: max_pages - 1]:
            html = _fetch(client, url)
            crawled += 1
            if html:
                page_emails = emails_from_html(html, domain)
                if page_emails:
                    board_pages.append(url)
                emails |= page_emails
                if any(h in url.lower() for h in BOARD_HINTS):
                    txt = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
                    if txt:
                        texts.append(txt[:8000])

        if render and not texts:
            for url in candidates[:3]:
                html = _render_html(url)
                if not html:
                    continue
                crawled += 1
                pe = emails_from_html(html, domain)
                if pe:
                    if url not in board_pages:
                        board_pages.append(url)
                    emails |= pe
                txt = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
                if txt and len(txt) > 400:
                    texts.append(txt[:8000])
                    break

    return {
        "domain": domain,
        "emails": sorted(emails),
        "pages_crawled": crawled,
        "board_pages": board_pages,
        "board_text": "\n\n".join(texts)[:16000],
        "platform": platform,
    }
