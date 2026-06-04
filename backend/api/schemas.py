import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class JobListItem(BaseModel):
    """Offre allégée pour la LISTE : sans `description` (jusqu'à 4000 car/offre).
    La carte ne l'affiche pas → on évite ~800 Ko de payload inutile sur 200 offres.
    Le détail (`JobOut`) la fournit, récupérée à l'ouverture de l'offre."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    company: str
    source: str
    url: str
    location: str
    logo_url: str | None = None
    score_heuristic: int | None = None
    score_ai: int | None
    # Champs normés extraits par Gemini, stockés en JSON sérialisé côté DB,
    # renvoyés ici en objet prêt à afficher (gardés : servent aux puces de la carte).
    details_ai: dict | None = None
    status: str
    notes: str | None
    scraped_at: datetime
    seen: bool
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    response: str | None = None
    hidden: bool = False

    @field_validator("details_ai", mode="before")
    @classmethod
    def _parse_details(cls, value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                return None
        return value


class JobOut(JobListItem):
    """Détail complet d'une offre (liste + description)."""

    description: str


class JobListOut(BaseModel):
    total: int
    items: list[JobListItem]


class StatusUpdate(BaseModel):
    status: str  # to_review | interested | applied | rejected


class NotesUpdate(BaseModel):
    notes: str


class TrackingUpdate(BaseModel):
    # Suivi de candidature. Champs optionnels : None efface la valeur.
    follow_up_at: datetime | None = None
    response: str | None = None


class HiddenUpdate(BaseModel):
    hidden: bool


class StatsOut(BaseModel):
    total: int
    by_source: dict[str, int]
    by_status: dict[str, int]
    by_day: dict[str, int]
    by_score: dict[str, int]  # buckets "0-19", "20-39", "40-59", "60-79", "80-100"


class ProgressOut(BaseModel):
    total: int
    scored: int  # offres avec un score IA
    extracted: int  # offres avec des champs normés extraits
    pending_scoring: int
    pending_extraction: int
    remaining_calls: int  # appels Gemini restants (1 appel par offre avec le tagger combiné)
    daily_quota: int  # quota Gemini estimé par jour
    estimated_days: int  # jours estimés avant tagging complet
    # Backfill descriptions LinkedIn
    linkedin_total: int = 0       # total offres LinkedIn actives (non masquées)
    linkedin_with_desc: int = 0   # dont celles avec une description récupérée
    linkedin_no_desc: int = 0     # en attente de backfill
