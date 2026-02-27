"""
Address check handler — the core feature.

Uses on-chain data + heuristic risk scoring. No Claude API calls.
"Deep analysis" button triggers Claude API on user's explicit request.
"""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.database.db import async_session
from bot.models.address_check import AddressCheck
from bot.services.chain_analyzer import analyze_address, detect_chain
from bot.services.risk_scorer import compute_risk_score
from bot.services.claude_agent import analyze_address_with_ai
from bot.services.gamification import get_or_create_user, award_check_xp, update_quest_progress

logger = logging.getLogger(__name__)

RISK_EMOJI = {
    "low": "🟢",
    "medium": "🟡",
    "high": "🟠",
    "critical": "🔴",
    "unknown": "⚪",
}

CHAIN_NAMES = {
    "ethereum": "Ethereum",
    "bsc": "BNB Chain",
    "bitcoin": "Bitcoin",
    "solana": "Solana",
    "tron": "Tron",
}


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /check <address> [chain] command."""
    if not context.args:
        await update.message.reply_text(
            "Отправь адрес для проверки:\n<code>/check 0x...</code>",
            parse_mode="HTML",
        )
        return

    address = context.args[0]
    chain = context.args[1] if len(context.args) > 1 else None

    await _do_check(update, address, chain)


async def handle_raw_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages that look like crypto addresses."""
    text = update.message.text.strip()

    if detect_chain(text) is not None:
        await _do_check(update, text, chain=None)


async def _do_check(update: Update, address: str, chain: str | None) -> None:
    """Core check logic — on-chain data + heuristic scoring, no API calls to Claude."""
    user = update.effective_user

    thinking_msg = await update.message.reply_text("🔍 Анализирую адрес...")

    try:
        # 1. Fetch on-chain data
        info = await analyze_address(address, chain)

        if info.error:
            await thinking_msg.edit_text(f"⚠️ Ошибка: {info.error}")
            return

        # 2. Compute risk score
        score, level, reasons = compute_risk_score(info)

        # 3. Build report (no AI)
        summary = _build_summary(info, score, level, reasons)

        # 4. Save to DB and process gamification
        async with async_session() as session:
            db_user = await get_or_create_user(
                session,
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
            )

            check = AddressCheck(
                user_id=db_user.id,
                address=address,
                chain=info.chain,
                risk_score=score,
                risk_level=level,
                balance=info.balance,
                tx_count=info.tx_count,
                first_seen=info.first_seen,
                last_active=info.last_active,
                ai_summary=None,
                labels=",".join(info.labels) if info.labels else None,
            )
            session.add(check)
            await session.commit()

            rewards = await award_check_xp(session, db_user, score)
            completed_quests = await update_quest_progress(session, db_user, info.chain, score)

        # 5. Append gamification
        xp_line = f"\n✨ +{rewards['xp_earned']} XP"
        if rewards["leveled_up"]:
            xp_line += f" | 🎉 Новый уровень: {rewards['new_level_name']}!"

        for ach in rewards["achievements"]:
            xp_line += f"\n🏆 Ачивка: {ach['icon']} {ach['title']} (+{ach['xp']} XP)"

        for quest in completed_quests:
            xp_line += f"\n📋 Квест выполнен: {quest['title']} (+{quest['xp']} XP)"

        summary += xp_line

        # 6. "Deep analysis" button — encodes address and chain into callback_data
        effective_chain = info.chain
        callback_data = f"deep:{effective_chain}:{address}"
        # Telegram callback_data max 64 bytes — truncate address if needed
        if len(callback_data) > 64:
            callback_data = f"deep:{effective_chain}:{address[:50]}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧠 Глубокий анализ (AI)", callback_data=callback_data)]
        ])

        await thinking_msg.edit_text(summary, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        logger.exception("Check failed")
        await thinking_msg.edit_text(f"😔 Что-то пошло не так: {e}")


async def deep_analysis_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'deep analysis' button — calls Claude API."""
    query = update.callback_query
    await query.answer()

    # Parse callback: deep:<chain>:<address>
    parts = query.data.split(":", 2)
    if len(parts) != 3:
        await query.message.reply_text("⚠️ Ошибка: не удалось прочитать адрес.")
        return

    _, chain, address = parts

    # Remove the button so it can't be pressed again
    await query.edit_message_reply_markup(reply_markup=None)

    thinking_msg = await query.message.reply_text("🧠 Запускаю глубокий AI-анализ...")

    try:
        # Re-fetch on-chain data for fresh context
        info = await analyze_address(address, chain)

        if info.error:
            await thinking_msg.edit_text(f"⚠️ Не удалось получить данные: {info.error}")
            return

        # Call Claude API
        ai_text = await analyze_address_with_ai(info)

        # Save AI summary to DB
        async with async_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(AddressCheck)
                .where(AddressCheck.address == address)
                .order_by(AddressCheck.created_at.desc())
                .limit(1)
            )
            check = result.scalar_one_or_none()
            if check:
                check.ai_summary = ai_text
                await session.commit()

        await thinking_msg.edit_text(
            f"🧠 <b>Глубокий анализ</b>\n\n{ai_text}",
            parse_mode="HTML",
        )

    except Exception as e:
        logger.exception("Deep analysis failed")
        await thinking_msg.edit_text(f"😔 AI-анализ не удался: {e}")


def _build_summary(info, score: float, level: str, reasons: list[str]) -> str:
    """Build address report from on-chain data + heuristics."""
    emoji = RISK_EMOJI.get(level, "⚪")
    chain_display = CHAIN_NAMES.get(info.chain, info.chain)
    age_str = info.first_seen.strftime("%Y-%m-%d") if info.first_seen else "н/д"
    last_str = info.last_active.strftime("%Y-%m-%d %H:%M UTC") if info.last_active else "н/д"

    short_addr = f"{info.address[:10]}...{info.address[-8:]}" if len(info.address) > 20 else info.address

    text = f"""{emoji} <b>Проверка адреса</b>

<b>Адрес:</b> <code>{short_addr}</code>
<b>Сеть:</b> {chain_display}
<b>Риск:</b> {score:.0f}/100 ({level})

<b>Баланс:</b> {info.balance}
<b>Транзакций:</b> {info.tx_count or 'н/д'}
<b>Первая активность:</b> {age_str}
<b>Последняя активность:</b> {last_str}"""

    if info.is_contract:
        text += "\n<b>Тип:</b> смарт-контракт"

    if info.labels:
        text += f"\n<b>Метки:</b> {', '.join(info.labels)}"

    if reasons:
        text += "\n\n<b>Наблюдения:</b>"
        for r in reasons:
            text += f"\n• {r}"

    return text


def register_check_handlers(app) -> None:
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CallbackQueryHandler(deep_analysis_callback, pattern=r"^deep:"))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_raw_address),
        group=1,
    )
