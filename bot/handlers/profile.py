"""
/profile handler.
"""

from telegram import Update, User as TgUser
from telegram.ext import CommandHandler, ContextTypes
from sqlalchemy import select

from bot.database.db import async_session
from bot.models.user import LEVEL_THRESHOLDS
from bot.models.achievement import UserAchievement, Achievement
from bot.services.gamification import get_or_create_user


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile command."""
    await show_profile(update.message, update.effective_user)


async def show_profile(message, tg_user: TgUser) -> None:
    """Show user profile. Called from /profile and from menu button."""
    async with async_session() as session:
        db_user = await get_or_create_user(
            session,
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )

        # Get achievements
        result = await session.execute(
            select(UserAchievement, Achievement)
            .join(Achievement)
            .where(UserAchievement.user_id == db_user.id)
        )
        achievements = result.all()

        # Progress bar
        next_level_xp = LEVEL_THRESHOLDS.get(db_user.level + 1, db_user.xp)
        current_level_xp = LEVEL_THRESHOLDS.get(db_user.level, 0)
        xp_range = next_level_xp - current_level_xp
        xp_progress = db_user.xp - current_level_xp
        progress_pct = (xp_progress / xp_range * 100) if xp_range > 0 else 100
        bar_filled = int(progress_pct / 10)
        progress_bar = "█" * bar_filled + "░" * (10 - bar_filled)

        text = f"""🕵️ <b>Профиль детектива</b>

<b>Имя:</b> {db_user.first_name or db_user.username or 'Аноним'}
<b>Уровень:</b> {db_user.level} — {db_user.level_name}
<b>XP:</b> {db_user.xp} / {next_level_xp}
[{progress_bar}] {progress_pct:.0f}%

<b>Статистика:</b>
📊 Проверок: {db_user.checks_count}
🔥 Стрик: {db_user.streak_days} дн.
"""

        if achievements:
            text += "\n<b>Ачивки:</b>\n"
            for ua, ach in achievements:
                text += f"{ach.icon} {ach.title}\n"
        else:
            text += "\n<i>Пока нет ачивок — начни проверять адреса!</i>"

    await message.reply_text(text, parse_mode="HTML")


def register_profile_handlers(app) -> None:
    app.add_handler(CommandHandler("profile", profile_command))
