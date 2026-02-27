"""
/start and onboarding flow.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CommandHandler, ContextTypes

from bot.database.db import async_session
from bot.services.gamification import get_or_create_user


WELCOME_MESSAGE = """
🔍 <b>Привет! Я TxPeek — твой AML-детектив.</b>

Я помогу тебе разобраться в мире криптовалют и безопасности:

📋 <b>Что я умею:</b>
• Проверить любой крипто-адрес (ETH, BTC, SOL, TRON)
• Оценить уровень риска транзакций
• Объяснить AML и compliance простым языком
• Выдавать квесты и ачивки за проверки

🎮 <b>Как начать:</b>
/check <code>адрес</code> — проверить адрес
/learn — узнать про AML
/quests — посмотреть квесты
/profile — твой профиль и прогресс
/leaderboard — топ детективов

Просто отправь мне крипто-адрес, и я всё расскажу! 🕵️
"""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user

    async with async_session() as session:
        await get_or_create_user(
            session,
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )

    # Remove any leftover ReplyKeyboard from previous bots
    await update.message.reply_text(
        "...",
        reply_markup=ReplyKeyboardRemove(),
    )

    keyboard = [
        [InlineKeyboardButton("📢 Наш канал", url="https://t.me/txpeek")],
    ]

    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = """
<b>📖 Команды TxPeek:</b>

/check <code>адрес</code> — проверить крипто-адрес
/check <code>адрес</code> ethereum — указать сеть явно
/learn <code>тема</code> — узнать про AML-тему
/quests — активные квесты
/profile — твой профиль
/leaderboard — топ детективов

<b>Поддерживаемые сети:</b>
• Ethereum (и EVM: BSC)
• Bitcoin
• Solana
• Tron

Или просто отправь мне адрес — я сам определю сеть! 🔎
"""
    await update.message.reply_text(help_text, parse_mode="HTML")


def register_start_handlers(app) -> None:
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
