"""
TxPeek — AML Detective Telegram Bot.

Entry point: can run in polling mode (dev) or webhook mode (production).
"""

import asyncio
import logging
import sys

import uvicorn
from telegram.ext import ApplicationBuilder
from telegram import BotCommand

from bot.config import settings
from bot.database.db import init_db
from bot.handlers import register_all_handlers

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_polling():
    """Run bot in polling mode (for development)."""
    logger.info("Starting TxPeek bot in polling mode...")

    # Initialize database
    await init_db()

    # Build bot application
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    register_all_handlers(app)

    # Run
    await app.initialize()
    await app.bot.set_my_commands([
        BotCommand("check", "Проверить крипто-адрес"),
        BotCommand("learn", "Обучение AML"),
        BotCommand("menu", "Главное меню"),
        BotCommand("help", "Помощь"),
    ])
    await app.start()
    await app.updater.start_polling()

    logger.info("TxPeek is running! Press Ctrl+C to stop.")

    # Keep running until interrupted
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


def run_webhook():
    """Run bot with webhook via FastAPI (for production)."""
    from api.main import create_app

    logger.info("Starting TxPeek bot in webhook mode...")

    fastapi_app = create_app()

    # Create bot app and attach to FastAPI state
    bot_app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    register_all_handlers(bot_app)
    fastapi_app.state.bot_app = bot_app

    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "polling"

    if mode == "webhook":
        run_webhook()
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
