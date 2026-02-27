"""
Gamification engine — XP, levels, achievements, streaks.
"""

from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User, LEVEL_NAMES
from bot.models.address_check import AddressCheck
from bot.models.achievement import Achievement, UserAchievement, DEFAULT_ACHIEVEMENTS

# XP rewards for various actions
XP_CHECK_ADDRESS = 20
XP_FIRST_CHECK_OF_DAY = 10  # Bonus
XP_FIND_RISKY = 30  # risk_score > 70


async def seed_achievements(session: AsyncSession) -> None:
    """Create default achievements if they don't exist."""
    for ach_data in DEFAULT_ACHIEVEMENTS:
        existing = await session.execute(
            select(Achievement).where(Achievement.code == ach_data["code"])
        )
        if not existing.scalar_one_or_none():
            session.add(Achievement(**ach_data))
    await session.commit()


async def get_or_create_user(session: AsyncSession, telegram_id: int, **kwargs) -> User:
    """Get existing user or create new one."""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(telegram_id=telegram_id, **kwargs)
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return user


async def award_check_xp(
    session: AsyncSession,
    user: User,
    risk_score: float,
) -> dict:
    """Award XP for an address check. Returns info about rewards."""
    rewards = {"xp_earned": 0, "leveled_up": False, "new_level": None, "achievements": []}

    xp = XP_CHECK_ADDRESS
    user.checks_count += 1

    # Streak tracking
    now = datetime.now(timezone.utc)
    if user.last_check_date:
        days_since = (now.date() - user.last_check_date.date()).days
        if days_since == 1:
            user.streak_days += 1
            xp += XP_FIRST_CHECK_OF_DAY
        elif days_since > 1:
            user.streak_days = 1
    else:
        user.streak_days = 1

    user.last_check_date = now

    # Bonus for finding risky addresses
    if risk_score > 70:
        xp += XP_FIND_RISKY

    rewards["xp_earned"] = xp
    leveled_up = user.add_xp(xp)
    rewards["leveled_up"] = leveled_up
    if leveled_up:
        rewards["new_level"] = user.level
        rewards["new_level_name"] = LEVEL_NAMES.get(user.level, "")

    # Check achievements
    new_achievements = await _check_achievements(session, user, risk_score)
    rewards["achievements"] = new_achievements

    await session.commit()
    return rewards


async def _check_achievements(
    session: AsyncSession,
    user: User,
    risk_score: float,
) -> list[dict]:
    """Check and unlock new achievements."""
    unlocked = []

    result = await session.execute(select(Achievement))
    all_achievements = result.scalars().all()

    result = await session.execute(
        select(UserAchievement.achievement_id).where(UserAchievement.user_id == user.id)
    )
    user_achievement_ids = {row for row in result.scalars().all()}

    for ach in all_achievements:
        if ach.id in user_achievement_ids:
            continue

        earned = False

        if ach.condition_type == "checks_total" and user.checks_count >= ach.condition_value:
            earned = True
        elif ach.condition_type == "streak" and user.streak_days >= ach.condition_value:
            earned = True
        elif ach.condition_type == "level" and user.level >= ach.condition_value:
            earned = True
        elif ach.condition_type == "risky_found" and risk_score > 70:
            earned = True
        elif ach.condition_type == "unique_chains":
            result = await session.execute(
                select(func.count(func.distinct(AddressCheck.chain))).where(
                    AddressCheck.user_id == user.id
                )
            )
            chain_count = result.scalar() or 0
            if chain_count >= ach.condition_value:
                earned = True

        if earned:
            user_ach = UserAchievement(user_id=user.id, achievement_id=ach.id)
            session.add(user_ach)
            user.add_xp(ach.xp_reward)
            unlocked.append(
                {"title": ach.title, "icon": ach.icon, "xp": ach.xp_reward}
            )

    return unlocked
