import math

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import settings
from ...db.models import Job
from ..deps import get_session
from ..schemas import ProgressOut, StatsOut

router = APIRouter(prefix="/jobs", tags=["stats"])

# Buckets de score pour le graphique de distribution
_SCORE_BUCKETS = [
    ("0-19", 0, 20),
    ("20-39", 20, 40),
    ("40-59", 40, 60),
    ("60-79", 60, 80),
    ("80-100", 80, 101),
]


@router.get("/stats", response_model=StatsOut)
def stats(session: Session = Depends(get_session)):
    # Stats sur les annonces actives uniquement (les masquées sont exclues).
    active = Job.hidden.isnot(True)
    total = session.execute(select(func.count(Job.id)).where(active)).scalar_one()

    by_source = dict(
        session.execute(
            select(Job.source, func.count(Job.id)).where(active).group_by(Job.source)
        ).all()
    )
    by_status = dict(
        session.execute(
            select(Job.status, func.count(Job.id)).where(active).group_by(Job.status)
        ).all()
    )
    day = func.strftime("%Y-%m-%d", Job.scraped_at)
    by_day = dict(
        session.execute(
            select(day, func.count(Job.id)).where(active).group_by(day).order_by(day)
        ).all()
    )

    by_score: dict[str, int] = {}
    for label, low, high in _SCORE_BUCKETS:
        count = session.execute(
            select(func.count(Job.id)).where(
                active,
                Job.score_ai.isnot(None),
                Job.score_ai >= low,
                Job.score_ai < high,
            )
        ).scalar_one()
        by_score[label] = count

    return StatsOut(
        total=total,
        by_source=by_source,
        by_status=by_status,
        by_day=by_day,
        by_score=by_score,
    )


@router.get("/progress", response_model=ProgressOut)
def progress(session: Session = Depends(get_session)):
    total = session.execute(select(func.count(Job.id))).scalar_one()
    scored = session.execute(
        select(func.count(Job.id)).where(Job.score_ai.isnot(None))
    ).scalar_one()
    extracted = session.execute(
        select(func.count(Job.id)).where(Job.details_ai.isnot(None))
    ).scalar_one()

    pending_scoring = total - scored
    pending_extraction = total - extracted

    # Avec le tagger combiné, chaque offre non taguée nécessite 1 seul appel Gemini
    # (scoring + extraction simultanés). Les offres déjà scorées sans extraction
    # (backward compat) nécessitent encore 1 appel d'extraction seule.
    remaining_calls = pending_extraction

    daily_quota = max(settings.gemini_daily_quota, 1)
    estimated_days = math.ceil(remaining_calls / daily_quota) if remaining_calls else 0

    return ProgressOut(
        total=total,
        scored=scored,
        extracted=extracted,
        pending_scoring=pending_scoring,
        pending_extraction=pending_extraction,
        remaining_calls=remaining_calls,
        daily_quota=daily_quota,
        estimated_days=estimated_days,
    )
