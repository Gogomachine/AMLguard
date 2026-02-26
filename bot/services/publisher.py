"""
Social media publisher — posts to Twitter/X and Telegram channel.
"""

import logging

import httpx
import tweepy

from bot.config import settings
from bot.services.claude_agent import generate_social_post

logger = logging.getLogger(__name__)


def _get_twitter_client() -> tweepy.Client | None:
    """Create Twitter API v2 client."""
    if not all([
        settings.twitter_api_key,
        settings.twitter_api_secret,
        settings.twitter_access_token,
        settings.twitter_access_secret,
    ]):
        return None

    return tweepy.Client(
        consumer_key=settings.twitter_api_key,
        consumer_secret=settings.twitter_api_secret,
        access_token=settings.twitter_access_token,
        access_token_secret=settings.twitter_access_secret,
    )


async def publish_to_telegram_channel(text: str) -> bool:
    """Publish a post to the Telegram channel."""
    if not settings.telegram_channel_id or not settings.telegram_bot_token:
        logger.warning("Telegram channel or bot token not configured")
        return False

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": settings.telegram_channel_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
            )
            data = resp.json()
            if data.get("ok"):
                logger.info("Published to Telegram channel")
                return True
            else:
                logger.error("Telegram channel post failed: %s", data)
                return False
    except httpx.HTTPError as e:
        logger.error("Telegram publish error: %s", e)
        return False


async def publish_to_twitter(text: str) -> bool:
    """Publish a tweet."""
    client = _get_twitter_client()
    if not client:
        logger.warning("Twitter not configured")
        return False

    try:
        client.create_tweet(text=text)
        logger.info("Published to Twitter")
        return True
    except tweepy.TweepyException as e:
        logger.error("Twitter publish error: %s", e)
        return False


async def publish_case(case_data: str) -> dict:
    """
    Generate and publish a case study to both platforms.
    Returns status for each platform.
    """
    results = {"telegram": False, "twitter": False}

    # Generate Telegram post
    tg_post = await generate_social_post(case_data, platform="telegram")
    results["telegram"] = await publish_to_telegram_channel(tg_post)

    # Generate shorter Twitter post
    tw_post = await generate_social_post(case_data, platform="twitter")
    results["twitter"] = await publish_to_twitter(tw_post)

    return results
