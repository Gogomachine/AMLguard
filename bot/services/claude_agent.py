"""
Claude-powered AML agent — the brain of TxPeek.

Provides:
- Friendly AML/compliance explanations
- Address risk analysis with AI reasoning
- Case investigation assistance
- Content generation for social media
"""

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
- Поддерживаешь и мотивируешь пользователей изучать AML
- Отвечаешь на русском, если пользователь пишет на русском

Правила:
- Никогда не даёшь финансовых советов
- Подчёркиваешь что анализ — это эвристика, а не финальный вердикт
- При высоком риске рекомендуешь обратиться к профессиональному AML-сервису
- Объясняешь терминологию, когда используешь её впервые
"""


def _format_address_context(info: AddressInfo, score: float, level: str, reasons: list[str]) -> str:
    """Format address data into context for Claude."""
    age_str = "неизвестен"
    if info.first_seen:
        age_days = (info.last_active or info.first_seen) and info.first_seen
        age_str = info.first_seen.strftime("%Y-%m-%d")

    last_active_str = info.last_active.strftime("%Y-%m-%d %H:%M UTC") if info.last_active else "неизвестно"

    return f"""Результаты проверки адреса:

Адрес: {info.address}
Сеть: {info.chain}
Баланс: {info.balance}
Количество транзакций: {info.tx_count or 'неизвестно'}
Первая активность: {age_str}
Последняя активность: {last_active_str}
Контракт: {'да' if info.is_contract else 'нет'}
Метки: {', '.join(info.labels) if info.labels else 'нет'}

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
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""Проанализируй этот крипто-адрес и дай краткий, понятный отчёт.
Включи:
1. Уровень риска (визуально: 🟢🟡🟠🔴)
2. Ключевые наблюдения (2-3 пункта)
3. Что это может означать простым языком
4. Рекомендации

{context}""",
            }
        ],
    )

    return message.content[0].text


async def explain_topic(topic: str) -> str:
    """Explain an AML/compliance topic in simple terms."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Объясни простым языком: {topic}",
            }
        ],
    )

    return message.content[0].text


async def chat(user_message: str, context: str = "") -> str:
    """General chat with the AML agent."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    system = SYSTEM_PROMPT
    if context:
        system += f"\n\nДополнительный контекст о пользователе:\n{context}"

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=600,
        system=system,
        messages=[
            {
                "role": "user",
                "content": user_message,
            }
        ],
    )

    return message.content[0].text


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

Пост должен быть:
- Информативным и цепляющим
- С практической пользой для читателей
- С призывом к действию (проверить свои адреса, подписаться)""",
            }
        ],
    )

    return message.content[0].text
