"""
Gamification engine — XP, levels, achievements, quests, streaks.
"""

from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User, LEVEL_NAMES
from bot.models.address_check import AddressCheck
from bot.models.achievement import Achievement, UserAchievement, DEFAULT_ACHIEVEMENTS
from bot.models.quest import Quest, UserQuest

# XP rewards for various actions
XP_CHECK_ADDRESS = 20
XP_FIRST_CHECK_OF_DAY = 10  # Bonus
XP_FIND_RISKY = 30  # risk_score > 70
XP_QUEST_BONUS = 50  # On top of quest reward


async def seed_achievements(session: AsyncSession) -> None:
    """Create default achievements if they don't exist."""
    for ach_data in DEFAULT_ACHIEVEMENTS:
        existing = await session.execute(
            select(Achievement).where(Achievement.code == ach_data["code"])
        )
        if not existing.scalar_one_or_none():
            session.add(Achievement(**ach_data))
    await session.commit()


async def seed_default_quests(session: AsyncSession) -> None:
    """Create initial quests if none exist."""
    existing = await session.execute(select(func.count(Quest.id)))
    if existing.scalar() > 0:
        return

    default_quests = [
        Quest(
            title="Первый взгляд",
            description="Проверь свой первый крипто-адрес",
            quest_type="daily",
            xp_reward=30,
            condition_type="check_count",
            condition_value=1,
        ),
        Quest(
            title="Тройная проверка",
            description="Проверь 3 разных адреса за день",
            quest_type="daily",
            xp_reward=50,
            condition_type="check_count",
            condition_value=3,
        ),
        Quest(
            title="Охотник за рисками",
            description="Найди адрес с уровнем риска выше 50",
            quest_type="weekly",
            xp_reward=100,
            condition_type="find_risky",
            condition_value=1,
        ),
        Quest(
            title="Мультичейн-исследователь",
            description="Проверь адреса в 3 разных сетях",
            quest_type="weekly",
            xp_reward=150,
            condition_type="check_chain",
            condition_value=3,
        ),
        Quest(
            title="Марафонец",
            description="Проверяй адреса 5 дней подряд",
            quest_type="weekly",
            xp_reward=200,
            condition_type="streak",
            condition_value=5,
        ),
    ]

    for quest in default_quests:
        session.add(quest)
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
    """
    Award XP for an address check. Returns info about rewards.
    """
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

    # Get all achievements
    result = await session.execute(select(Achievement))
    all_achievements = result.scalars().all()

    # Get user's existing achievements
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


async def update_quest_progress(
    session: AsyncSession,
    user: User,
    check_chain: str,
    risk_score: float,
) -> list[dict]:
    """Update quest progress after an address check. Returns completed quests."""
    completed = []

    # Get active quests
    result = await session.execute(select(Quest).where(Quest.is_active.is_(True)))
    quests = result.scalars().all()

    for quest in quests:
        # Get or create user quest
        result = await session.execute(
            select(UserQuest).where(
                UserQuest.user_id == user.id,
                UserQuest.quest_id == quest.id,
                UserQuest.is_completed.is_(False),
            )
        )
        uq = result.scalar_one_or_none()

        if not uq:
            uq = UserQuest(user_id=user.id, quest_id=quest.id, progress=0)
            session.add(uq)

        # Update progress based on condition
        should_increment = False

        if quest.condition_type == "check_count":
            should_increment = True
        elif quest.condition_type == "find_risky" and risk_score > 50:
            should_increment = True
        elif quest.condition_type == "check_chain":
            # Count unique chains checked today
            result = await session.execute(
                select(func.count(func.distinct(AddressCheck.chain))).where(
                    AddressCheck.user_id == user.id
                )
            )
            unique = result.scalar() or 0
            uq.progress = unique
        elif quest.condition_type == "streak":
            uq.progress = user.streak_days

        if should_increment:
            uq.progress += 1

        if uq.progress >= quest.condition_value and not uq.is_completed:
            uq.is_completed = True
            uq.completed_at = datetime.now(timezone.utc)
            user.add_xp(quest.xp_reward)
            completed.append({"title": quest.title, "xp": quest.xp_reward})

    await session.commit()
    return completed


async def get_leaderboard(session: AsyncSession, limit: int = 10) -> list[dict]:
    """Get top users by XP."""
    result = await session.execute(
        select(User).order_by(User.xp.desc()).limit(limit)
    )
    users = result.scalars().all()

    return [
        {
            "rank": i + 1,
            "username": u.username or u.first_name or f"User #{u.telegram_id}",
            "level": u.level,
            "level_name": u.level_name,
            "xp": u.xp,
            "checks": u.checks_count,
        }
        for i, u in enumerate(users)
    ]
