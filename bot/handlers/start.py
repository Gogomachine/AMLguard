"""
/start, /help, and main menu.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.database.db import async_session
from bot.services.gamification import get_or_create_user


WELCOME_MESSAGE = """
🔍 <b>Привет! Я TxPeek — твой AML-детектив.</b>

Я помогу тебе разобраться в мире криптовалют и безопасности:

• Проверить любой крипто-адрес (ETH, BTC, SOL, TRON)
• Оценить уровень риска
• Объяснить AML и compliance простым языком

Выбери действие ниже или просто отправь мне крипто-адрес 👇
"""


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 Проверить адрес", callback_data="menu:check")],
        [InlineKeyboardButton("❓ Задать вопрос", callback_data="menu:ask")],
        [InlineKeyboardButton("👤 Профиль", callback_data="menu:profile")],
    ])


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
    await update.message.reply_text("...", reply_markup=ReplyKeyboardRemove())

    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle main menu button presses."""
    query = update.callback_query
    await query.answer()

    action = query.data.replace("menu:", "")

    if action == "check":
        await query.message.reply_text(
            "🔎 Отправь мне крипто-адрес — я определю сеть автоматически.\n\n"
            "Или используй команду:\n"
            "<code>/check 0x...</code>",
            parse_mode="HTML",
        )

    elif action == "ask":
        await query.message.reply_text(
            "❓ <b>Задай вопрос про AML и крипто-безопасность</b>\n\n"
            "Выбери готовую тему — /learn\n"
            "Или задай свой вопрос:\n"
            "<code>/learn что такое compliance</code>",
            parse_mode="HTML",
        )

    elif action == "profile":
        # Trigger profile handler directly
        from bot.handlers.profile import show_profile
        await show_profile(query.message, update.effective_user)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = """
<b>📖 Команды TxPeek:</b>

/check <code>адрес</code> — проверить крипто-адрес
/learn — темы про AML
/learn <code>вопрос</code> — задать свой вопрос (AI)
/profile — твой профиль
/menu — главное меню

<b>Поддерживаемые сети:</b>
• Ethereum (и EVM: BSC)
• Bitcoin
• Solana
• Tron

Или просто отправь адрес — я сам определю сеть! 🔎
"""
    await update.message.reply_text(help_text, parse_mode="HTML")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu command — show main menu."""
    await update.message.reply_text(
        "Выбери действие 👇",
        reply_markup=main_menu_keyboard(),
    )


def register_start_handlers(app) -> None:
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))
