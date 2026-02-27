"""
/digest — manually trigger AML news digest.
"""

import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.services.news_digest import generate_and_post_digest

logger = logging.getLogger(__name__)


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /digest command — manually generate and post a digest."""
    await update.message.reply_text(
        "📰 Генерирую AML-дайджест... Это может занять минуту.",
    )

    try:
        success = await generate_and_post_digest(period="ручной")
        if success:
            await update.message.reply_text(
                "✅ Дайджест опубликован в канале!"
            )
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
