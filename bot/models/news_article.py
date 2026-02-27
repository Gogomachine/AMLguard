"""
Parsed news article — stores scraped AML news to avoid duplicates.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.db import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(255))  # domain name
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # when posted to channel
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
