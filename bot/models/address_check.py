from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.db import Base


class AddressCheck(Base):
    __tablename__ = "address_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    address: Mapped[str] = mapped_column(String(255), index=True)
    chain: Mapped[str] = mapped_column(String(50))  # ethereum, bitcoin, solana, tron

    # Risk assessment
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    risk_level: Mapped[str] = mapped_column(String(20), default="unknown")  # low, medium, high, critical

    # Address info
    balance: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tx_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_active: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # AI analysis
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    labels: Mapped[str | None] = mapped_column(String(500), nullable=True)  # comma-separated

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="address_checks")  # noqa: F821
