"""
AML news parser — scrapes RSS feeds and HTML pages from AML-themed websites.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TxPeek-AML-Bot/1.0; "
        "+https://github.com/txpeek)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Timeout for each HTTP request (seconds)
REQUEST_TIMEOUT = 20


@dataclass
class ParsedArticle:
    """A single article parsed from a news source."""

    url: str
    title: str
    snippet: str  # first paragraph or description
    source: str  # domain
    published_at: datetime | None = None


# ---------------------------------------------------------------------------
# RSS parsing (via BeautifulSoup on XML)
# ---------------------------------------------------------------------------

def _parse_rss_date(date_str: str | None) -> datetime | None:
    """Try to parse an RSS date string."""
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
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
        published_at = _parse_rss_date(pub_date.get_text(strip=True) if pub_date else None)

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

    for tag in article_tags:
        link = tag.find("a", href=True) if tag.name == "article" else (
            tag.find("a", href=True) or (tag.parent.find("a", href=True) if tag.parent else None)
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
            continue

        # Try to find a snippet nearby
        snippet = ""
        p_tag = tag.find("p") if tag.name == "article" else (
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
# Public API
# ---------------------------------------------------------------------------

async def fetch_articles(url: str) -> list[ParsedArticle]:
    """
    Fetch and parse articles from a single URL.
    Auto-detects RSS vs HTML content.
    """
    domain = urlparse(url).netloc
    try:
        async with httpx.AsyncClient(
            headers=HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.text
    except httpx.HTTPError as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return []

    content_type = resp.headers.get("content-type", "")

    # Detect RSS/Atom
    if (
        "xml" in content_type
        or "rss" in content_type
        or "atom" in content_type
        or content.lstrip().startswith("<?xml")
        or "<rss" in content[:500]
        or "<feed" in content[:500]
    ):
        articles = _parse_rss(content, domain)
        logger.info("Parsed %d articles from RSS: %s", len(articles), domain)
        return articles

    # Fallback to HTML scraping
    articles = _parse_html(content, url, domain)
    logger.info("Parsed %d articles from HTML: %s", len(articles), domain)
    return articles


async def fetch_all_sources(urls: list[str]) -> list[ParsedArticle]:
    """Fetch articles from all configured sources, deduplicate by URL."""
    all_articles: list[ParsedArticle] = []
    seen_urls: set[str] = set()

    for url in urls:
        try:
            articles = await fetch_articles(url)
            for article in articles:
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    all_articles.append(article)
        except Exception as e:
            logger.error("Error processing source %s: %s", url, e)

    logger.info("Total articles fetched: %d from %d sources", len(all_articles), len(urls))
    return all_articles
