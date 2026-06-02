import math

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import settings
from ...db.models import Job
from ..deps import get_session
from ..schemas import ProgressOut, StatsOut

router = APIRouter(prefix="/jobs", tags=["stats"])


@router.get("/stats", response_model=StatsOut)
def stats(session: Session = Depends(get_session)):
    total = session.execute(select(func.count(Job.id))).scalar_one()

    by_source = dict(
        session.execute(select(Job.source, func.count(Job.id)).group_by(Job.source)).all()
    )
    by_status = dict(
        session.execute(select(Job.status, func.count(Job.id)).group_by(Job.status)).all()
    )
    day = func.strftime("%Y-%m-%d", Job.scraped_at)
    by_day = dict(
        session.execute(select(day, func.count(Job.id)).group_by(day).order_by(day)).all()
    )
    return StatsOut(total=total, by_source=by_source, by_status=by_status, by_day=by_day)


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
    remaining_calls = pending_scoring + pending_extraction  # 1 appel Gemini chacun

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
