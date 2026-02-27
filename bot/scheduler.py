"""
APScheduler setup — runs periodic tasks (news digest, etc.).
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def _run_async(coro_func, *args):
    """Wrapper to run async function from sync APScheduler callback."""
    loop = asyncio.get_event_loop()
    loop.create_task(coro_func(*args))


async def _morning_digest():
    from bot.services.news_digest import generate_and_post_digest

    logger.info("Running morning digest job...")
    try:
        await generate_and_post_digest(period="утро")
    except Exception as e:
        logger.error("Morning digest failed: %s", e)


async def _evening_digest():
    from bot.services.news_digest import generate_and_post_digest

    logger.info("Running evening digest job...")
    try:
        await generate_and_post_digest(period="вечер")
    except Exception as e:
        logger.error("Evening digest failed: %s", e)


def start_scheduler() -> AsyncIOScheduler:
    """Configure and start the scheduler with digest jobs."""
    morning_hour = settings.digest_morning_hour
    evening_hour = settings.digest_evening_hour

    scheduler.add_job(
        _morning_digest,
        trigger=CronTrigger(hour=morning_hour, minute=0, timezone="UTC"),
        id="morning_digest",
        replace_existing=True,
    )

    scheduler.add_job(
        _evening_digest,
        trigger=CronTrigger(hour=evening_hour, minute=0, timezone="UTC"),
        id="evening_digest",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started: morning digest at %02d:00 UTC, evening at %02d:00 UTC",
        morning_hour,
        evening_hour,
    )
    return scheduler
