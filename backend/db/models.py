from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    company: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, index=True)
    url: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    # URL du logo entreprise fournie par la source (LinkedIn) ; sinon NULL → repli initiales.
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Score heuristique local (étage 1, gratuit) : pertinence provisoire 0-100 calculée
    # au stockage. Sert de classement par défaut + priorité de passage Gemini.
    score_heuristic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_ai: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Champs normés extraits par Gemini (JSON sérialisé) — voir backend/ai/extractor.py
    details_ai: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String, default="to_review", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    seen: Mapped[bool] = mapped_column(Boolean, default=False)
    # Masquée par l'utilisateur (archivage) : exclue des listes mais conservée en base
    # pour que la dédup empêche sa ré-import (et donc un nouveau scoring Gemini).
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Suivi de candidature
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # auto à "applied"
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # date de relance
    # réponse reçue : None/pending = en attente, positive, negative, ghosted (sans réponse)
    response: Mapped[str | None] = mapped_column(String, nullable=True)
