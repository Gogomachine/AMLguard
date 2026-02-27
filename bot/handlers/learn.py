"""
/learn handler — educational AML content.

Predefined topics answered locally (no API cost).
Free-form questions via /learn <вопрос> go to Claude API.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.services.claude_agent import explain_topic

# Predefined answers — no API call needed
TOPICS = {
    "aml_basics": {
        "title": "Что такое AML",
        "short": "AML основы",
        "text": (
            "<b>AML (Anti-Money Laundering)</b> — это набор законов, правил и процедур, "
            "которые мешают преступникам маскировать незаконные деньги под легальные.\n\n"
            "Простыми словами: если кто-то украл деньги или заработал их на наркотиках, "
            "он не может просто положить их в банк. AML-система должна это поймать.\n\n"
            "<b>В крипто AML работает так:</b>\n"
            "• Биржи проверяют откуда пришли монеты\n"
            "• Специальные сервисы отслеживают подозрительные адреса\n"
            "• Если адрес связан с даркнетом или миксером — транзакцию могут заблокировать\n\n"
            "<b>Зачем это тебе?</b>\n"
            "Если ты получишь крипту с «грязного» адреса, твой аккаунт на бирже "
            "могут заморозить. Поэтому проверка адресов — это не паранойя, а гигиена."
        ),
    },
    "kyc": {
        "title": "Что такое KYC",
        "short": "KYC",
        "text": (
            "<b>KYC (Know Your Customer)</b> — процедура проверки личности клиента.\n\n"
            "Когда биржа просит паспорт и селфи — это KYC. Нужно, чтобы:\n"
            "• Убедиться, что ты — это ты\n"
            "• Мошенник не мог открыть аккаунт на чужое имя\n"
            "• Биржа выполняла закон своей юрисдикции\n\n"
            "<b>Уровни KYC:</b>\n"
            "• <b>Базовый</b> — email + телефон (маленькие лимиты)\n"
            "• <b>Продвинутый</b> — документ + селфи (полный доступ)\n"
            "• <b>Enhanced</b> — подтверждение дохода (для крупных сумм)\n\n"
            "KYC и AML идут рука об руку: KYC — это «кто ты», AML — «откуда деньги»."
        ),
    },
    "mixer": {
        "title": "Миксеры и тумблеры",
        "short": "Миксеры",
        "text": (
            "<b>Крипто-миксер (тумблер)</b> — сервис, который смешивает монеты "
            "разных пользователей, чтобы запутать след.\n\n"
            "<b>Как работает:</b>\n"
            "1. Ты отправляешь 1 BTC в миксер\n"
            "2. Миксер смешивает твои монеты с сотнями других\n"
            "3. Ты получаешь 1 BTC обратно, но уже «другие» монеты\n\n"
            "<b>Примеры:</b>\n"
            "• <b>Tornado Cash</b> (Ethereum) — заблокирован OFAC в 2022\n"
            "• <b>Wasabi Wallet</b> (Bitcoin) — CoinJoin протокол\n"
            "• <b>Sinbad</b> — заблокирован в 2023\n\n"
            "<b>Почему это важно:</b>\n"
            "Если ты получишь крипту, которая прошла через миксер — "
            "AML-системы это увидят и могут пометить как высокий риск."
        ),
    },
    "travel_rule": {
        "title": "Travel Rule",
        "short": "Travel Rule",
        "text": (
            "<b>Travel Rule</b> — правило, по которому при переводе крипты выше определённой "
            "суммы отправитель и получатель должны обмениваться идентификационными данными.\n\n"
            "<b>Как это работает:</b>\n"
            "Если ты переводишь >$1000 с одной биржи на другую, биржи обязаны "
            "передать друг другу: имя отправителя, имя получателя, номера аккаунтов.\n\n"
            "Это как банковский SWIFT-перевод, только для крипты.\n\n"
            "<b>Кого касается:</b>\n"
            "• Централизованные биржи (Binance, Coinbase и т.д.)\n"
            "• Крипто-кастодианы\n"
            "• P2P площадки с лицензией\n\n"
            "DeFi и некастодиальные кошельки пока в серой зоне, но регуляторы "
            "работают и над этим."
        ),
    },
    "sanctions": {
        "title": "Санкции и OFAC",
        "short": "Санкции",
        "text": (
            "<b>OFAC SDN List</b> — список лиц и организаций, с которыми запрещено "
            "вести дела (санкции США).\n\n"
            "<b>В крипто это значит:</b>\n"
            "• Некоторые крипто-адреса внесены в SDN List\n"
            "• Если ты отправишь туда крипту (или получишь оттуда) — это нарушение\n"
            "• Биржи обязаны блокировать такие транзакции\n\n"
            "<b>Примеры санкционных адресов:</b>\n"
            "• Адреса Tornado Cash (2022)\n"
            "• Адреса северокорейской группы Lazarus\n"
            "• Адреса связанные с даркнет-маркетами\n\n"
            "<b>Совет:</b> Перед крупной транзакцией проверь адрес получателя — "
            "это займёт секунду, а спасти может от серьёзных проблем."
        ),
    },
    "risk_scoring": {
        "title": "Оценка риска адресов",
        "short": "Risk scoring",
        "text": (
            "<b>Risk scoring</b> — автоматическая оценка «чистоты» крипто-адреса.\n\n"
            "<b>Что анализируется:</b>\n"
            "• <b>Возраст адреса</b> — новые адреса подозрительнее старых\n"
            "• <b>Паттерны транзакций</b> — странные объёмы, частота, суммы\n"
            "• <b>Связи</b> — контактировал ли адрес с миксерами, даркнетом\n"
            "• <b>Баланс vs активность</b> — нулевой баланс при 1000 транзакций = подозрительно\n"
            "• <b>Метки</b> — известные биржи, мошенники, контракты\n\n"
            "<b>Уровни риска:</b>\n"
            "🟢 Low (0-25) — всё чисто\n"
            "🟡 Medium (25-50) — стоит присмотреться\n"
            "🟠 High (50-75) — осторожно\n"
            "🔴 Critical (75-100) — лучше не связываться\n\n"
            "Именно так работает команда /check в этом боте!"
        ),
    },
    "defi_risks": {
        "title": "AML-риски в DeFi",
        "short": "DeFi риски",
        "text": (
            "<b>DeFi</b> (децентрализованные финансы) создаёт уникальные AML-вызовы.\n\n"
            "<b>Основные риски:</b>\n"
            "• <b>Нет KYC</b> — любой может пользоваться протоколом анонимно\n"
            "• <b>Cross-chain мосты</b> — переводят активы между сетями, запутывая след\n"
            "• <b>Flash loans</b> — мгновенные займы используются в атаках\n"
            "• <b>Rug pulls</b> — создатели проекта сливают ликвидность\n\n"
            "<b>Как защитить себя:</b>\n"
            "• Проверяй контракт через /check перед взаимодействием\n"
            "• Смотри возраст контракта — если создан вчера, будь осторожен\n"
            "• Проверяй аудиты проекта\n"
            "• Не доверяй контрактам с большим количеством транзакций "
            "но нулевым балансом"
        ),
    },
    "nft_laundering": {
        "title": "Отмывание через NFT",
        "short": "NFT отмывание",
        "text": (
            "<b>NFT</b> стали инструментом для отмывания денег из-за субъективности цен.\n\n"
            "<b>Схемы:</b>\n"
            "• <b>Wash trading</b> — покупаешь свой же NFT с другого кошелька "
            "за завышенную цену, создавая «легальную» прибыль\n"
            "• <b>Fake collections</b> — создают коллекцию, продают за крипту, "
            "выводят через биржу\n"
            "• <b>Royalty abuse</b> — высокие роялти на контракте, прокручивают "
            "продажи между своими кошельками\n\n"
            "<b>Красные флаги:</b>\n"
            "• NFT продаётся в разы дороже floor price\n"
            "• Покупатель и продавец связаны (одинаковые паттерны транзакций)\n"
            "• Коллекция без истории, но с огромными объёмами\n\n"
            "AML-сервисы уже умеют отслеживать NFT-транзакции."
        ),
    },
}


async def learn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /learn [topic].

    Without args — show topic menu (local answers, no API).
    With args — send free-form question to Claude API.
    """
    if context.args:
        topic = " ".join(context.args)
        await _explain_via_api(update, topic)
        return

    # Show topic menu — all answered locally
    keyboard = []
    row = []
    for code, data in TOPICS.items():
        row.append(InlineKeyboardButton(data["short"], callback_data=f"learn:{code}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        "📚 <b>Выбери тему или задай свой вопрос:</b>\n"
        "<code>/learn что такое compliance</code>\n\n"
        "Кнопки ниже — быстрые ответы. Свой вопрос — через Claude AI.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def learn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle topic button press — local answer, no API."""
    query = update.callback_query
    await query.answer()

    code = query.data.replace("learn:", "")
    topic_data = TOPICS.get(code)

    if not topic_data:
        await query.message.reply_text("Тема не найдена.")
        return

    await query.message.reply_text(topic_data["text"], parse_mode="HTML")


async def _explain_via_api(update: Update, topic: str) -> None:
    """Send free-form question to Claude API."""
    msg = await update.message.reply_text("🧠 Спрашиваю у Claude...")

    try:
        response = await explain_topic(topic)
        await msg.edit_text(response, parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"😔 Не удалось получить ответ: {e}")


def register_learn_handlers(app) -> None:
    app.add_handler(CommandHandler("learn", learn_command))
    app.add_handler(CallbackQueryHandler(learn_callback, pattern=r"^learn:"))
