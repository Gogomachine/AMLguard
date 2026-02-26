"""
/quests handler — quest system.
"""

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from sqlalchemy import select

from bot.database.db import async_session
from bot.models.quest import Quest, UserQuest
from bot.services.gamification import get_or_create_user


async def quests_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show active quests and progress."""
    user = update.effective_user

    async with async_session() as session:
        db_user = await get_or_create_user(
            session,
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )

        # Get active quests with user progress
        result = await session.execute(select(Quest).where(Quest.is_active.is_(True)))
        quests = result.scalars().all()

        text = "📋 <b>Активные квесты:</b>\n\n"

        if not quests:
            text += "Пока нет активных квестов. Скоро появятся!"
        else:
            for quest in quests:
                # Get user progress
                result = await session.execute(
                    select(UserQuest).where(
                        UserQuest.user_id == db_user.id,
                        UserQuest.quest_id == quest.id,
                    )
                )
                uq = result.scalar_one_or_none()

                progress = uq.progress if uq else 0
                completed = uq.is_completed if uq else False

                status = "✅" if completed else f"📊 {progress}/{quest.condition_value}"
                type_badge = {"daily": "🌅", "weekly": "📅", "special": "⭐"}.get(
                    quest.quest_type, "📋"
                )

                text += (
                    f"{type_badge} <b>{quest.title}</b> {status}\n"
                    f"   {quest.description}\n"
                    f"   Награда: +{quest.xp_reward} XP\n\n"
                )

    await update.message.reply_text(text, parse_mode="HTML")


def register_quest_handlers(app) -> None:
    app.add_handler(CommandHandler("quests", quests_command))
