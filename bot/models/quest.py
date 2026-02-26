from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.db import Base


class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    quest_type: Mapped[str] = mapped_column(String(50))  # daily, weekly, special
    xp_reward: Mapped[int] = mapped_column(Integer, default=50)

    # Conditions (JSON-like string for simplicity)
    condition_type: Mapped[str] = mapped_column(String(50))  # check_count, find_risky, check_chain, streak
    condition_value: Mapped[int] = mapped_column(Integer, default=1)
    condition_chain: Mapped[str | None] = mapped_column(String(50), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserQuest(Base):
    __tablename__ = "user_quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id"))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="user_quests")  # noqa: F821
    quest: Mapped["Quest"] = relationship()
