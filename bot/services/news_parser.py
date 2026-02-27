"""
AML news parser — scrapes RSS feeds and HTML pages from AML-themed websites.
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Rotate User-Agent to reduce bot-detection blocks
_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
]

REQUEST_TIMEOUT = 25
MAX_RETRIES = 2


def _headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }


@dataclass
class ParsedArticle:
    """A single article parsed from a news source."""

    url: str
    title: str
    snippet: str  # first paragraph or description
    source: str  # domain
    published_at: datetime | None = None


# ---------------------------------------------------------------------------
# RSS parsing (via BeautifulSoup + lxml-xml)
# ---------------------------------------------------------------------------

def _parse_rss_date(date_str: str | None) -> datetime | None:
    """Try to parse an RSS date string."""
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        # Try ISO-8601 (Atom feeds)
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None


def _parse_rss(xml_text: str, source_domain: str) -> list[ParsedArticle]:
    """Parse RSS/Atom XML into a list of articles."""
    # Use lxml-xml for proper XML parsing; fallback to html.parser
    try:
        soup = BeautifulSoup(xml_text, "xml")
    except Exception:
        soup = BeautifulSoup(xml_text, "html.parser")
    articles: list[ParsedArticle] = []

    # RSS 2.0 — <item>
    items = soup.find_all("item")
    if not items:
        # Atom — <entry>
        items = soup.find_all("entry")

    for item in items[:15]:  # limit to latest 15
        # Title
        title_tag = item.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        if not title:
            continue

        # Link
        link_tag = item.find("link")
        if link_tag:
            url = link_tag.get("href") or link_tag.get_text(strip=True)
        else:
            url = ""
        if not url:
            continue

        # Description / summary / content
        desc_tag = (
            item.find("description")
            or item.find("summary")
            or item.find("content")
            or item.find("content:encoded")
        )
        snippet = ""
        if desc_tag:
            raw = desc_tag.get_text(" ", strip=True)
            # Strip HTML inside description
            inner = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
            snippet = inner[:500]

        # Date (try both cases for RSS vs Atom, xml vs html parser)
        pub_date = (
            item.find("pubDate")
            or item.find("pubdate")
            or item.find("published")
            or item.find("updated")
            or item.find("dc:date")
        )
        published_at = _parse_rss_date(
            pub_date.get_text(strip=True) if pub_date else None
        )

        articles.append(
            ParsedArticle(
                url=url,
                title=title,
                snippet=snippet,
                source=source_domain,
                published_at=published_at,
            )
        )

    return articles


# ---------------------------------------------------------------------------
# HTML scraping (generic heuristic)
# ---------------------------------------------------------------------------

def _parse_html(html_text: str, base_url: str, source_domain: str) -> list[ParsedArticle]:
    """
    Heuristic HTML parser — finds article links on a news page.
    Looks for <article>, <h2>/<h3> with <a> tags, common news patterns.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    articles: list[ParsedArticle] = []
    seen_urls: set[str] = set()

    # Strategy 1: <article> tags
    article_tags = soup.find_all("article", limit=20)

    # Strategy 2: headings with links (h2, h3)
    if not article_tags:
        article_tags = soup.find_all(["h2", "h3"], limit=30)

    # Strategy 3: divs with common news-card class patterns
    if not article_tags:
        for cls in ("post", "card", "news-item", "blog-item", "entry"):
            found = soup.find_all(
                "div", class_=lambda c: c and cls in c, limit=20
            )
            if found:
                article_tags = found
                break

    for tag in article_tags:
        link = tag.find("a", href=True) if tag.name in ("article", "div") else (
            tag.find("a", href=True)
            or (tag.parent.find("a", href=True) if tag.parent else None)
        )
        if not link or not link.get("href"):
            continue

        href = link["href"]
        # Make absolute URL
        if href.startswith("/"):
            parsed = urlparse(base_url)
            href = f"{parsed.scheme}://{parsed.netloc}{href}"
        elif not href.startswith("http"):
            continue

        if href in seen_urls:
            continue
        seen_urls.add(href)

        title = link.get_text(strip=True)
        if not title or len(title) < 10:
            # Try to get title from a heading inside the container
            heading = tag.find(["h2", "h3", "h4"])
            if heading:
                title = heading.get_text(strip=True)
        if not title or len(title) < 10:
            continue

        # Try to find a snippet nearby
        snippet = ""
        p_tag = tag.find("p") if tag.name in ("article", "div") else (
            tag.find_next_sibling("p")
        )
        if p_tag:
            snippet = p_tag.get_text(" ", strip=True)[:300]

        articles.append(
            ParsedArticle(
                url=href,
                title=title,
                snippet=snippet,
                source=source_domain,
            )
        )

    return articles[:15]


# ---------------------------------------------------------------------------
# RSS auto-discovery from HTML page
# ---------------------------------------------------------------------------

def _discover_rss_from_html(html_text: str, base_url: str) -> str | None:
    """Look for <link rel='alternate' type='application/rss+xml'> in HTML."""
    soup = BeautifulSoup(html_text, "html.parser")
    for link in soup.find_all("link", rel="alternate"):
        link_type = link.get("type", "")
        if "rss" in link_type or "atom" in link_type or "xml" in link_type:
            href = link.get("href", "")
            if href.startswith("/"):
                parsed = urlparse(base_url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            if href.startswith("http"):
                return href
    return None


# ---------------------------------------------------------------------------
# HTTP fetching with retry
# ---------------------------------------------------------------------------

async def _fetch_url(url: str) -> tuple[str, str] | None:
    """
    Fetch URL content with retries.
    Returns (content, content_type) or None on failure.
    """
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(
                headers=_headers(),
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text, resp.headers.get("content-type", "")
        except httpx.HTTPStatusError as e:
            # Don't retry on 403/404 — it's intentional blocking
            if e.response.status_code in (403, 404, 451):
                logger.warning("Blocked by %s (HTTP %d)", url, e.response.status_code)
                return None
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
            else:
                logger.warning("Failed to fetch %s after %d attempts: %s", url, MAX_RETRIES + 1, e)
        except httpx.HTTPError as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
            else:
                logger.warning("Failed to fetch %s: %s", url, e)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_articles(url: str) -> list[ParsedArticle]:
    """
    Fetch and parse articles from a single URL.
    Auto-detects RSS vs HTML content. If HTML, tries RSS auto-discovery.
    """
    domain = urlparse(url).netloc
    result = await _fetch_url(url)
    if not result:
        return []

    content, content_type = result

    # Detect RSS/Atom
    is_rss = (
        "xml" in content_type
        or "rss" in content_type
        or "atom" in content_type
        or content.lstrip().startswith("<?xml")
        or "<rss" in content[:500]
        or "<feed" in content[:500]
    )

    if is_rss:
        articles = _parse_rss(content, domain)
        logger.info("Parsed %d articles from RSS: %s", len(articles), domain)
        return articles

    # HTML page — try to discover RSS feed first
    rss_url = _discover_rss_from_html(content, url)
    if rss_url:
        logger.info("Discovered RSS feed: %s", rss_url)
        rss_result = await _fetch_url(rss_url)
        if rss_result:
            articles = _parse_rss(rss_result[0], domain)
            if articles:
                logger.info("Parsed %d articles from discovered RSS: %s", len(articles), domain)
                return articles

    # Fallback to HTML scraping
    articles = _parse_html(content, url, domain)
    logger.info("Parsed %d articles from HTML: %s", len(articles), domain)
    return articles


async def _safe_fetch(url: str) -> list[ParsedArticle]:
    """Fetch articles from a single source, catching all errors."""
    try:
        return await fetch_articles(url)
    except Exception as e:
        logger.error("Error processing source %s: %s", url, e)
        return []


async def fetch_all_sources(urls: list[str]) -> list[ParsedArticle]:
    """Fetch articles from all configured sources in parallel, deduplicate by URL."""
    results = await asyncio.gather(*[_safe_fetch(url) for url in urls])

    all_articles: list[ParsedArticle] = []
    seen_urls: set[str] = set()
    sources_ok = 0

    for articles in results:
        if articles:
            sources_ok += 1
        for article in articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                all_articles.append(article)

    logger.info(
        "Total articles fetched: %d from %d/%d sources",
        len(all_articles), sources_ok, len(urls),
    )
    return all_articles
