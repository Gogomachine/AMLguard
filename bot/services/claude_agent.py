"""
Claude-powered AML agent — the brain of TxPeek.
"""

import re

import anthropic

from bot.config import settings
from bot.services.chains.base import AddressInfo
from bot.services.risk_scorer import compute_risk_score

SYSTEM_PROMPT = """\
Ты — TxPeek, дружелюбный AML-агент и крипто-детектив.
Твоя миссия — помогать людям разбираться в безопасности криптовалют, AML и compliance.

Твой стиль:
- Говоришь просто и понятно, без занудства
- Используешь аналогии из реальной жизни
- Добавляешь немного юмора, но остаёшься профессиональным
- Используешь эмоджи для визуального оформления
- Отвечаешь на русском, если пользователь пишет на русском

КРИТИЧЕСКИ ВАЖНЫЕ правила форматирования:
- НИКОГДА не используй символы * и # в ответах
- Для выделения используй HTML-теги: <b>жирный</b>, <i>курсив</i>
- Списки оформляй через символ •
- Ответ должен быть компактным и уместиться в ОДНО сообщение Telegram (до 4000 символов)
- Не используй Markdown — только чистый HTML

Правила по содержанию:
- Никогда не даёшь финансовых советов
- Подчёркиваешь что анализ — это эвристика, а не финальный вердикт
- При высоком риске рекомендуешь обратиться к профессиональному AML-сервису
"""


def _clean_response(text: str) -> str:
    """Strip markdown artifacts from AI response, keep HTML only."""
    # Remove markdown bold/italic
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    # Remove markdown headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove markdown links [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Remove leftover * and #
    text = text.replace("*", "").replace("#", "")
    # Truncate to Telegram limit
    if len(text) > 4000:
        text = text[:3950] + "\n\n...ответ сокращён"
    return text.strip()


def _format_address_context(info: AddressInfo, score: float, level: str, reasons: list[str]) -> str:
    """Format address data into context for Claude."""
    age_str = info.first_seen.strftime("%Y-%m-%d") if info.first_seen else "неизвестен"
    last_active_str = info.last_active.strftime("%Y-%m-%d %H:%M UTC") if info.last_active else "неизвестно"

    name_tag_str = info.name_tag or "нет"
    counterparties_str = (
        chr(10).join(f"  • {c}" for c in info.counterparties)
        if info.counterparties
        else "нет подозрительных"
    )

    return f"""Результаты проверки адреса:

Адрес: {info.address}
Сеть: {info.chain}
Баланс: {info.balance}
Количество транзакций: {info.tx_count or 'неизвестно'}
Первая активность: {age_str}
Последняя активность: {last_active_str}
Контракт: {'да' if info.is_contract else 'нет'}
Метки: {', '.join(info.labels) if info.labels else 'нет'}
Метка с эксплорера (Etherscan name tag): {name_tag_str}

Контрагенты (подозрительные адреса из транзакций):
{counterparties_str}

Предварительная оценка риска: {score:.0f}/100 ({level})
Причины:
{chr(10).join(f'- {r}' for r in reasons) if reasons else '- Нет явных признаков риска'}
"""


async def analyze_address_with_ai(info: AddressInfo) -> str:
    """Get AI analysis of an address based on on-chain data."""
    score, level, reasons = compute_risk_score(info)
    context = _format_address_context(info, score, level, reasons)

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=700,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""Проанализируй этот крипто-адрес и дай краткий, понятный отчёт.

Формат ответа (строго HTML, без markdown):
1. Уровень риска с эмоджи (🟢🟡🟠🔴)
2. Ключевые наблюдения (2-3 пункта через •)
3. Что это может означать простым языком
4. Короткая рекомендация

Ответ должен быть компактным — до 2000 символов.

{context}""",
            }
        ],
    )

    return _clean_response(message.content[0].text)


async def explain_topic(topic: str) -> str:
    """Explain an AML/compliance topic in simple terms."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Объясни простым языком: {topic}\n\n"
                    "Формат: чистый HTML (без markdown). Используй <b> для выделения, "
                    "• для списков, эмоджи для визуала. Ответ до 2000 символов."
                ),
            }
        ],
    )

    return _clean_response(message.content[0].text)


async def generate_social_post(case_data: str, platform: str = "telegram") -> str:
    """Generate a social media post about an AML case or news."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    length_hint = "до 280 символов" if platform == "twitter" else "до 1000 символов"

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=400,
        system=SYSTEM_PROMPT + f"\n\nТы сейчас пишешь пост для {platform}. Длина: {length_hint}.",
        messages=[
            {
                "role": "user",
                "content": f"""Напиши engaging пост на основе этих данных:

{case_data}

Формат: чистый текст с эмоджи, без markdown.""",
            }
        ],
    )

    return _clean_response(message.content[0].text)
