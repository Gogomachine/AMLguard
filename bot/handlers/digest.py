"""
/digest — manually trigger AML news digest.
"""

import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.services.news_digest import generate_digest

logger = logging.getLogger(__name__)


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /digest command — generate digest and send it directly to the user."""
    await update.message.reply_text(
        "📰 Генерирую AML-дайджест... Это может занять минуту.",
    )

    try:
        post = await generate_digest(period="по запросу")
        if post:
            await update.message.reply_text(post, parse_mode="HTML")
        else:
            await update.message.reply_text(
                "⚠️ База статей пуста. Попробуйте позже — "
                "источники ещё не были загружены."
            )
    except Exception as e:
        logger.error("Manual digest failed: %s", e)
        await update.message.reply_text(
            f"❌ Ошибка при генерации дайджеста: {e}"
        )


def register_digest_handlers(app):
    """Register digest-related handlers."""
    app.add_handler(CommandHandler("digest", digest_command))
