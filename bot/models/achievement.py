from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.db import Base


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(10), default="🏆")
    xp_reward: Mapped[int] = mapped_column(Integer, default=100)

    condition_type: Mapped[str] = mapped_column(String(50))  # checks_total, risky_found, streak, level
    condition_value: Mapped[int] = mapped_column(Integer, default=1)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id"))
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="user_achievements")  # noqa: F821
    achievement: Mapped["Achievement"] = relationship()


# Default achievements to seed
DEFAULT_ACHIEVEMENTS = [
    {
        "code": "first_check",
        "title": "Первый шаг",
        "description": "Проверь свой первый крипто-адрес",
        "icon": "🔍",
        "xp_reward": 50,
        "condition_type": "checks_total",
        "condition_value": 1,
    },
    {
        "code": "ten_checks",
        "title": "На вкус и цвет",
        "description": "Проверь 10 адресов",
        "icon": "📊",
        "xp_reward": 200,
        "condition_type": "checks_total",
        "condition_value": 10,
    },
    {
        "code": "fifty_checks",
        "title": "AML-маньяк",
        "description": "Проверь 50 адресов",
        "icon": "🔬",
        "xp_reward": 500,
        "condition_type": "checks_total",
        "condition_value": 50,
    },
    {
        "code": "risky_finder",
        "title": "Нюхач",
        "description": "Найди первый подозрительный адрес (risk > 70)",
        "icon": "🐕",
        "xp_reward": 150,
        "condition_type": "risky_found",
        "condition_value": 1,
    },
    {
        "code": "streak_3",
        "title": "Привычка",
        "description": "Проверяй адреса 3 дня подряд",
        "icon": "🔥",
        "xp_reward": 100,
        "condition_type": "streak",
        "condition_value": 3,
    },
    {
        "code": "streak_7",
        "title": "Неделя бдительности",
        "description": "Проверяй адреса 7 дней подряд",
        "icon": "⚡",
        "xp_reward": 300,
        "condition_type": "streak",
        "condition_value": 7,
    },
    {
        "code": "multichain",
        "title": "Мультивселенная",
        "description": "Проверь адреса в 4 разных сетях",
        "icon": "🌐",
        "xp_reward": 250,
        "condition_type": "unique_chains",
        "condition_value": 4,
    },
    {
        "code": "level_5",
        "title": "Детектив",
        "description": "Достигни 5-го уровня",
        "icon": "🕵️",
        "xp_reward": 500,
        "condition_type": "level",
        "condition_value": 5,
    },
]
