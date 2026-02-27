"""
AML News Digest — scrapes sources, summarises with Claude, posts to Telegram.

Scheduled twice daily (morning + evening) via APScheduler.
"""

import logging
from datetime import datetime, timezone

import anthropic
from sqlalchemy import select

from bot.config import settings
from bot.database.db import async_session
from bot.models.news_article import NewsArticle
from bot.services.news_parser import ParsedArticle, fetch_all_sources

FALLBACK_LIMIT = 5
from bot.services.publisher import publish_to_telegram_channel

logger = logging.getLogger(__name__)

# Default AML news sources — user can override via NEWS_SOURCES env var
# RSS feeds preferred (more reliable); HTML pages as fallback
DEFAULT_SOURCES: list[str] = [
    # Blockchain analytics (RSS)
    "https://www.chainalysis.com/blog/feed",
    "https://www.elliptic.co/blog/rss.xml",
    # Blockchain analytics (HTML — React SPA, may need JS rendering)
    "https://www.trmlabs.com/category/insights",
    "https://www.trmlabs.com/category/trm-investigations",
    "https://www.trmlabs.com/category/foundations",
    # AML / Compliance organizations (RSS)
    "https://www.acamstoday.org/feed/",
    # Regulators (HTML — server-rendered, scrapable)
    "https://www.fatf-gafi.org/en/the-fatf/news.html",
    # Crypto media — policy & regulation (RSS)
    "https://www.coindesk.com/arc/outboundfeeds/rss/?category=policy",
    # Russian-language crypto media (RSS)
    "https://forklog.com/feed",
]


def _get_sources() -> list[str]:
    """Get list of news source URLs from settings or defaults."""
    if settings.news_sources:
        return [s.strip() for s in settings.news_sources.split(",") if s.strip()]
    return DEFAULT_SOURCES


async def _filter_new_articles(articles: list[ParsedArticle]) -> list[ParsedArticle]:
    """Filter out articles that already exist in the database."""
    if not articles:
        return []

    urls = [a.url for a in articles]

    async with async_session() as session:
        result = await session.execute(
            select(NewsArticle.url).where(NewsArticle.url.in_(urls))
        )
        existing_urls = set(result.scalars().all())

    new_articles = [a for a in articles if a.url not in existing_urls]
    logger.info("Filtered: %d total → %d new articles", len(articles), len(new_articles))
    return new_articles


async def _save_articles(articles: list[ParsedArticle]) -> None:
    """Save new articles to the database."""
    async with async_session() as session:
        for article in articles:
            db_article = NewsArticle(
                url=article.url,
                title=article.title,
                summary=article.snippet,
                source=article.source,
                published_at=article.published_at,
            )
            session.add(db_article)
        await session.commit()


async def _get_latest_from_db(limit: int = FALLBACK_LIMIT) -> list[ParsedArticle]:
    """Fetch the most recent articles from the database as a fallback."""
    async with async_session() as session:
        result = await session.execute(
            select(NewsArticle)
            .order_by(NewsArticle.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()

    return [
        ParsedArticle(
            title=row.title,
            url=row.url,
            snippet=row.summary or "",
            source=row.source,
            published_at=row.published_at,
        )
        for row in rows
    ]


async def _mark_as_posted(urls: list[str]) -> None:
    """Update posted_at timestamp for articles included in digest."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        result = await session.execute(
            select(NewsArticle).where(NewsArticle.url.in_(urls))
        )
        for article in result.scalars().all():
            article.posted_at = now
        await session.commit()


async def _summarize_for_digest(articles: list[ParsedArticle]) -> str:
    """Use Claude to create a digest post from a batch of articles."""
    # Build context from articles
    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"\n{i}. {a.title}\n"
        if a.snippet:
            articles_text += f"   {a.snippet[:300]}\n"
        articles_text += f"   URL: {a.url}\n"
        articles_text += f"   Источник: {a.source}\n"

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1200,
        system=(
            "Ты — редактор AML-дайджеста для Telegram-канала TxPeek. "
            "Твоя задача — создать краткий дайджест из новостей по теме AML, "
            "комплаенс и криптовалютного регулирования.\n\n"
            "Правила:\n"
            "- Пиши НА РУССКОМ, даже если источники на английском\n"
            "- Формат: каждая новость — буллет-поинт (•) с заголовком и 1-2 предложениями сути\n"
            "- Указывай источник в скобках после каждой новости\n"
            "- Добавь тематические эмоджи\n"
            "- НЕ используй markdown (* и #), только чистый HTML: <b>, <i>\n"
            "- Общая длина — до 3000 символов\n"
            "- В конце добавь хэштеги: #AML #Compliance #Crypto"
        ),
        messages=[
            {
                "role": "user",
                "content": f"Составь AML-дайджест из этих новостей:\n{articles_text}",
            }
        ],
    )

    return message.content[0].text


def _format_digest(summary: str, period: str) -> str:
    """Wrap the AI summary into a formatted digest post."""
    date_str = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    header = f"📰 <b>AML Дайджест</b> — {date_str} ({period})\n\n"
    footer = "\n\n🤖 <i>Подготовлено TxPeek AI</i>"
    return header + summary + footer


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_digest(period: str = "утро") -> str | None:
    """
    Generate digest text: fetch → filter → save → summarise → format.
    Returns formatted digest string, or None if nothing to build from.
    """
    sources = _get_sources()
    if not sources:
        logger.warning("No news sources configured. Set NEWS_SOURCES in .env")
        return None

    # 1. Fetch articles from all sources
    all_articles = await fetch_all_sources(sources)

    # 2. Filter out already seen articles
    new_articles = await _filter_new_articles(all_articles) if all_articles else []

    # 3. Save new articles to database
    if new_articles:
        await _save_articles(new_articles)

    # 4. Pick top articles for digest (max 7); fall back to latest from DB
    if new_articles:
        digest_articles = new_articles[:7]
    else:
        logger.info("No new articles — falling back to latest %d from DB", FALLBACK_LIMIT)
        digest_articles = await _get_latest_from_db()
        if not digest_articles:
            logger.warning("Database is empty — nothing to build a digest from")
            return None

    # 5. Summarize with Claude
    try:
        summary = await _summarize_for_digest(digest_articles)
    except Exception as e:
        logger.error("Failed to generate digest summary: %s", e)
        return None

    # 6. Format
    return _format_digest(summary, period)


async def generate_and_post_digest(period: str = "утро") -> bool:
    """
    Full pipeline for scheduled posting: generate digest and publish to channel.
    Returns True if digest was posted successfully.
    """
    post = await generate_digest(period)
    if not post:
        return False

    success = await publish_to_telegram_channel(post)

    if success:
        logger.info("Digest posted successfully to channel")
    else:
        logger.error("Failed to post digest to Telegram channel")

    return success
