from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    company: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, index=True)
    url: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str] = mapped_column(Text, default="")

    summary_ai: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_ai: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String, default="to_review", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    seen: Mapped[bool] = mapped_column(Boolean, default=False)
