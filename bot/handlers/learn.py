"""
/learn handler — educational AML content.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.services.claude_agent import explain_topic

# Predefined popular topics
TOPICS = {
    "aml_basics": "Что такое AML (Anti-Money Laundering) и зачем это нужно",
    "kyc": "Что такое KYC и почему биржи требуют документы",
    "mixer": "Что такое миксеры и тумблеры в крипто",
    "travel_rule": "Что такое Travel Rule в криптовалютах",
    "sanctions": "Как работают санкции в крипто и что такое OFAC SDN List",
    "risk_scoring": "Как работает оценка риска крипто-адресов",
    "defi_risks": "AML-риски в DeFi протоколах",
    "nft_laundering": "Отмывание денег через NFT — как это работает",
}


async def learn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /learn [topic]."""
    if context.args:
        topic = " ".join(context.args)
        await _explain(update, topic)
        return

    # Show topic menu
    keyboard = []
    row = []
    for code, title in TOPICS.items():
        short = title.split("—")[0].split("и ")[0].strip()[:30]
        row.append(InlineKeyboardButton(short, callback_data=f"learn:{code}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        "📚 <b>Выбери тему или напиши свой вопрос:</b>\n"
        "<code>/learn что такое compliance</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def learn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle topic button press."""
    query = update.callback_query
    await query.answer()

    code = query.data.replace("learn:", "")
    topic = TOPICS.get(code, code)

    await query.message.reply_text("🧠 Думаю...")
    response = await explain_topic(topic)
    await query.message.reply_text(response, parse_mode="HTML")


async def _explain(update: Update, topic: str) -> None:
    """Explain a topic using Claude."""
    msg = await update.message.reply_text("🧠 Думаю...")

    try:
        response = await explain_topic(topic)
        await msg.edit_text(response, parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"😔 Не удалось получить ответ: {e}")


def register_learn_handlers(app) -> None:
    app.add_handler(CommandHandler("learn", learn_command))
    app.add_handler(CallbackQueryHandler(learn_callback, pattern=r"^learn:"))
