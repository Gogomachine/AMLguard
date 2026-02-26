from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.db import Base

# Level thresholds: XP required to reach each level
LEVEL_THRESHOLDS = {
    1: 0,        # Новичок
    2: 100,      # Наблюдатель
    3: 300,      # Следопыт
    4: 700,      # Аналитик
    5: 1500,     # Детектив
    6: 3000,     # Инспектор
    7: 6000,     # AML Эксперт
    8: 12000,    # Whale Inspector
    9: 25000,    # Легенда
    10: 50000,   # Грандмастер
}

LEVEL_NAMES = {
    1: "Новичок",
    2: "Наблюдатель",
    3: "Следопыт",
    4: "Аналитик",
    5: "Детектив",
    6: "Инспектор",
    7: "AML Эксперт",
    8: "Whale Inspector",
    9: "Легенда",
    10: "Грандмастер",
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    checks_count: Mapped[int] = mapped_column(Integer, default=0)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_check_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    address_checks: Mapped[list["AddressCheck"]] = relationship(back_populates="user")  # noqa: F821
    user_quests: Mapped[list["UserQuest"]] = relationship(back_populates="user")  # noqa: F821
    user_achievements: Mapped[list["UserAchievement"]] = relationship(  # noqa: F821
        back_populates="user"
    )

    @property
    def level_name(self) -> str:
        return LEVEL_NAMES.get(self.level, "Новичок")

    @property
    def xp_to_next_level(self) -> int:
        next_level = self.level + 1
        if next_level > 10:
            return 0
        return LEVEL_THRESHOLDS[next_level] - self.xp

    def add_xp(self, amount: int) -> bool:
        """Add XP and return True if leveled up."""
        self.xp += amount
        leveled_up = False
        while self.level < 10 and self.xp >= LEVEL_THRESHOLDS.get(self.level + 1, float("inf")):
            self.level += 1
            leveled_up = True
        return leveled_up
