"""
Address check handler — the core feature.
"""

import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

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

    # Quick check: does this look like an address?
    if detect_chain(text) is not None:
        await _do_check(update, text, chain=None)


async def _do_check(update: Update, address: str, chain: str | None) -> None:
    """Core check logic."""
    user = update.effective_user

    # Send "thinking" message
    thinking_msg = await update.message.reply_text("🔍 Анализирую адрес, секунду...")

    try:
        # 1. Fetch on-chain data
        info = await analyze_address(address, chain)

        if info.error:
            await thinking_msg.edit_text(f"⚠️ Ошибка: {info.error}")
            return

        # 2. Compute risk score
        score, level, reasons = compute_risk_score(info)

        # 3. Get AI analysis
        try:
            ai_summary = await analyze_address_with_ai(info)
        except Exception as e:
            logger.warning("AI analysis failed: %s", e)
            ai_summary = _build_fallback_summary(info, score, level, reasons)

        # 4. Save to DB and process gamification
        async with async_session() as session:
            db_user = await get_or_create_user(
                session,
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
            )

            # Save address check
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
                ai_summary=ai_summary,
                labels=",".join(info.labels) if info.labels else None,
            )
            session.add(check)
            await session.commit()

            # Award XP
            rewards = await award_check_xp(session, db_user, score)

            # Update quests
            completed_quests = await update_quest_progress(session, db_user, info.chain, score)

        # 5. Build response
        response = ai_summary

        # Add gamification footer
        xp_line = f"\n\n✨ +{rewards['xp_earned']} XP"
        if rewards["leveled_up"]:
            xp_line += f" | 🎉 Новый уровень: {rewards['new_level_name']}!"

        for ach in rewards["achievements"]:
            xp_line += f"\n🏆 Ачивка: {ach['icon']} {ach['title']} (+{ach['xp']} XP)"

        for quest in completed_quests:
            xp_line += f"\n📋 Квест выполнен: {quest['title']} (+{quest['xp']} XP)"

        response += xp_line

        await thinking_msg.edit_text(response, parse_mode="HTML")

    except Exception as e:
        logger.exception("Check failed")
        await thinking_msg.edit_text(f"😔 Что-то пошло не так: {e}")


def _build_fallback_summary(info, score: float, level: str, reasons: list[str]) -> str:
    """Build a summary without AI when Claude is unavailable."""
    emoji = RISK_EMOJI.get(level, "⚪")
    age_str = info.first_seen.strftime("%Y-%m-%d") if info.first_seen else "неизвестно"
    last_str = info.last_active.strftime("%Y-%m-%d") if info.last_active else "неизвестно"

    text = f"""{emoji} <b>Проверка адреса</b>

<b>Адрес:</b> <code>{info.address[:8]}...{info.address[-6:]}</code>
<b>Сеть:</b> {info.chain}
<b>Риск:</b> {score:.0f}/100 ({level})

<b>Баланс:</b> {info.balance}
<b>Транзакций:</b> {info.tx_count or 'н/д'}
<b>Первая активность:</b> {age_str}
<b>Последняя активность:</b> {last_str}
"""

    if reasons:
        text += "\n<b>Наблюдения:</b>\n"
        text += "\n".join(f"• {r}" for r in reasons)

    return text


def register_check_handlers(app) -> None:
    app.add_handler(CommandHandler("check", check_command))
    # Handle raw addresses sent as text (low priority, after other handlers)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_raw_address),
        group=1,
    )
