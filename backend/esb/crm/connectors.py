"""Deterministic source connectors for the dossier pipeline. No LLM here —
each returns structured results the pipeline logs and later hands to the
extraction seam. All are free / no-key.
"""
from __future__ import annotations

import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

_PAGE_DELAY_SECONDS = 2.0  # politeness pacing between paginated requests to the same engine

UA = "DevonBot/0.1 (+ESB; aj@effectiveschoolboards.com)"
# Search engines and many CMS sites block obvious bots — use a real browser UA there.
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


@dataclass
class Doc:
    source: str          # wikipedia | web | news
    method: str
    query: str
    url: str
    title: str = ""
    text: str = ""
    snippet: str = ""
    found: bool = field(default=False)


def _client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": UA}, timeout=15, follow_redirects=True)


def _browser() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9",
                 "Accept": "text/html,application/xhtml+xml"},
        timeout=15, follow_redirects=True)


def wikipedia(name: str) -> list[Doc]:
    """Wikipedia REST summary if a confident page exists."""
    out: list[Doc] = []
    try:
        with _client() as c:
            s = c.get("https://en.wikipedia.org/w/api.php", params={
                "action": "query", "list": "search", "srsearch": name,
                "format": "json", "srlimit": 1})
            hits = s.json().get("query", {}).get("search", [])
            if not hits:
                return [Doc("wikipedia", "standard_source", name, "", found=False)]
            title = hits[0]["title"]
            # Guard: only accept if the surname plausibly appears in the page title,
            # so non-notable names don't match an unrelated top hit.
            surname = name.replace('"', "").split()[-1].lower() if name.split() else ""
            if surname and surname not in title.lower():
                return [Doc("wikipedia", "standard_source", name, "", found=False)]
            r = c.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}")
            if r.status_code == 200:
                j = r.json()
                url = j.get("content_urls", {}).get("desktop", {}).get("page", "")
                out.append(Doc("wikipedia", "standard_source", name, url,
                               title=title, text=j.get("extract", ""), found=bool(j.get("extract"))))
    except Exception:
        pass
    return out or [Doc("wikipedia", "standard_source", name, "", found=False)]


def _ddg_lite(c: httpx.Client, query: str, limit: int) -> list[Doc]:
    """Page 1 only — DDG lite's pagination is a stateful POST carrying a
    per-session vqd token forward, too fragile to replicate reliably
    (verified 2026-07-01: naive token replay silently returns zero
    results rather than erroring, which is worse than not paging at
    all). Still a valuable engine for its distinct index coverage."""
    r = c.get("https://lite.duckduckgo.com/lite/", params={"q": query})
    soup = BeautifulSoup(r.text, "html.parser")
    out: list[Doc] = []
    for a in soup.select("a.result-link")[:limit]:
        href = a.get("href", "")
        real = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]
        if real.startswith("http"):
            out.append(Doc("web", "ddg_lite", query, real, title=a.get_text(strip=True), found=True))
    return out


def _bing(c: httpx.Client, query: str, limit: int, page: int = 1) -> list[Doc]:
    first = (page - 1) * limit + 1
    r = c.get("https://www.bing.com/search", params={"q": query, "count": limit, "first": first, "setlang": "en"})
    soup = BeautifulSoup(r.text, "html.parser")
    out: list[Doc] = []
    for li in soup.select("li.b_algo")[:limit]:
        a = li.select_one("h2 a")
        if not a or not a.get("href", "").startswith("http"):
            continue
        snip = li.select_one(".b_caption p") or li.select_one("p")
        out.append(Doc("web", "bing", query, a["href"], title=a.get_text(strip=True),
                       snippet=snip.get_text(" ", strip=True) if snip else "", found=True))
    return out


def _mojeek(c: httpx.Client, query: str, limit: int, page: int = 1) -> list[Doc]:
    """Verified 2026-07-01: clean GET-based pagination via s=(page-1)*10+1,
    no session/token state needed — the most reliable engine for deep
    (10-page) paging."""
    params = {"q": query}
    if page > 1:
        params["s"] = (page - 1) * 10 + 1
    r = c.get("https://www.mojeek.com/search", params=params)
    soup = BeautifulSoup(r.text, "html.parser")
    out: list[Doc] = []
    for li in soup.select("ul.results-standard li, .results li")[:limit]:
        a = li.select_one("a.title") or li.select_one("h2 a")
        if not a or not a.get("href", "").startswith("http"):
            continue
        snip = li.select_one("p.s") or li.select_one("p")
        out.append(Doc("web", "mojeek", query, a["href"], title=a.get_text(strip=True),
                       snippet=snip.get_text(" ", strip=True) if snip else "", found=True))
    return out


def _brave(c: httpx.Client, query: str, limit: int, page: int = 1) -> list[Doc]:
    """Brave Search API — documented offset-based pagination, no scraping
    fragility. No-ops (empty list) without an API key."""
    from esb.core.config import settings
    if not settings.brave_search_api_key:
        return []
    try:
        r = c.get("https://api.search.brave.com/res/v1/web/search", params={
            "q": query, "count": limit, "offset": page - 1,
        }, headers={"Accept": "application/json", "X-Subscription-Token": settings.brave_search_api_key})
        if r.status_code != 200:
            return []
        results = r.json().get("web", {}).get("results", [])
    except Exception:
        return []
    return [
        Doc("web", "brave", query, item.get("url", ""), title=item.get("title", ""),
            snippet=item.get("description", ""), found=True)
        for item in results if item.get("url", "").startswith("http")
    ]


def web_search(query: str, limit: int = 5) -> list[Doc]:
    """Resilient single-page web search: rotate free engines with a browser
    UA; first that yields wins. No key required. Engines block bots
    intermittently, so we fall through rather than retry the same one."""
    for engine in (_ddg_lite, _bing, _mojeek):
        try:
            with _browser() as c:
                out = engine(c, query, limit)
            if out:
                return out
        except Exception:
            continue
    return []


def deep_web_search(query: str, pages: int = 10, per_page: int = 10) -> list[Doc]:
    """Exhaustive search for the dossier pipeline: pages Mojeek (and Brave,
    if keyed) up to `pages` deep — the two engines with reliable
    pagination — plus a single page each from DDG lite and Bing for their
    distinct index coverage. Deduplicates by URL. This is what "go at
    least 10 pages deep" means in practice given which engines actually
    support it without fragile session-token replication (see
    RESEARCH_PLAN.md §2)."""
    seen: set[str] = set()
    out: list[Doc] = []

    def _add(docs: list[Doc]) -> None:
        for d in docs:
            if d.url and d.url not in seen:
                seen.add(d.url)
                out.append(d)

    with _browser() as c:
        for page in range(1, pages + 1):
            if page > 1:
                time.sleep(_PAGE_DELAY_SECONDS)
            try:
                page_docs = _mojeek(c, query, per_page, page=page)
            except Exception:
                page_docs = []
            if not page_docs:
                break  # ran out of results, or blocked — no point paging further
            _add(page_docs)

        for page in range(1, pages + 1):
            if page > 1:
                time.sleep(_PAGE_DELAY_SECONDS)
            try:
                page_docs = _brave(c, query, per_page, page=page)
            except Exception:
                page_docs = []
            if not page_docs:
                break
            _add(page_docs)

        for engine in (_ddg_lite, _bing):
            try:
                _add(engine(c, query, per_page))
            except Exception:
                continue

    return out


def news(query: str, limit: int = 6) -> list[Doc]:
    """Google News RSS — free, no key. Great for 'district in trouble' signals."""
    out: list[Doc] = []
    try:
        url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + "&hl=en-US&gl=US&ceid=US:en"
        with _client() as c:
            r = c.get(url)
            root = ET.fromstring(r.text)
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = (item.findtext("description") or "").strip()
                snippet = BeautifulSoup(desc, "html.parser").get_text(" ", strip=True)[:300]
                out.append(Doc("news", "news", query, link, title=title, snippet=snippet, found=True))
                if len(out) >= limit:
                    break
    except Exception:
        pass
    return out


_MIN_TEXT_LEN = 200  # below this, a plain fetch likely hit a JS-only shell


def _extract_text(html: str, max_chars: int) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)[:max_chars]


def fetch_text(url: str, max_chars: int = 8000) -> str:
    """Fetch a page and return cleaned visible text (for the extraction seam).

    Falls back to headless-Chromium rendering if the plain fetch returns
    suspiciously little text — a common sign of a JS-built page (state
    report-card dashboards, modern district sites) that returns an empty
    shell to a non-JS HTTP client."""
    try:
        with _browser() as c:
            r = c.get(url)
            if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
                text = _extract_text(r.text, max_chars)
                if len(text) >= _MIN_TEXT_LEN:
                    return text
    except Exception:
        pass

    from esb.crm.headless import render_html
    html = render_html(url)
    if not html:
        return ""
    try:
        return _extract_text(html, max_chars)
    except Exception:
        return ""
