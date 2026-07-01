"""Deterministic source connectors for the dossier pipeline. No LLM here —
each returns structured results the pipeline logs and later hands to the
extraction seam. All are free / no-key.
"""
from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

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
    r = c.get("https://lite.duckduckgo.com/lite/", params={"q": query})
    soup = BeautifulSoup(r.text, "html.parser")
    out: list[Doc] = []
    for a in soup.select("a.result-link")[:limit]:
        href = a.get("href", "")
        real = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]
        if real.startswith("http"):
            out.append(Doc("web", "ddg_lite", query, real, title=a.get_text(strip=True), found=True))
    return out


def _bing(c: httpx.Client, query: str, limit: int) -> list[Doc]:
    r = c.get("https://www.bing.com/search", params={"q": query, "count": limit, "setlang": "en"})
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


def _mojeek(c: httpx.Client, query: str, limit: int) -> list[Doc]:
    r = c.get("https://www.mojeek.com/search", params={"q": query})
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


def web_search(query: str, limit: int = 5) -> list[Doc]:
    """Resilient web search: rotate free engines with a browser UA; first that
    yields wins. No key. Engines block bots intermittently, so we fall through."""
    for engine in (_ddg_lite, _bing, _mojeek):
        try:
            with _browser() as c:
                out = engine(c, query, limit)
            if out:
                return out
        except Exception:
            continue
    return []


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


def fetch_text(url: str, max_chars: int = 8000) -> str:
    """Fetch a page and return cleaned visible text (for the extraction seam)."""
    try:
        with _browser() as c:
            r = c.get(url)
            if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
                return ""
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return soup.get_text(" ", strip=True)[:max_chars]
    except Exception:
        return ""
