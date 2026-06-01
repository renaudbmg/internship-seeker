from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.models import Job
from ..deps import get_session
from ..schemas import StatsOut

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
