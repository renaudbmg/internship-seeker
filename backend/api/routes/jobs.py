from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...db.models import Job
from ..deps import get_session
from ..schemas import JobListOut, JobOut, NotesUpdate, StatusUpdate

router = APIRouter(prefix="/jobs", tags=["jobs"])

VALID_STATUSES = {"to_review", "interested", "applied", "rejected"}


@router.get("", response_model=JobListOut)
def list_jobs(
    session: Session = Depends(get_session),
    source: str | None = None,
    status: str | None = None,
    score_min: int | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Job)
    if source:
        stmt = stmt.where(Job.source == source)
    if status:
        stmt = stmt.where(Job.status == status)
    if score_min is not None:
        stmt = stmt.where(Job.score_ai >= score_min)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.description.ilike(pattern),
            )
        )

    total = len(session.execute(stmt).scalars().all())
    stmt = stmt.order_by(Job.score_ai.is_(None), Job.score_ai.desc(), Job.scraped_at.desc())
    items = session.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return JobListOut(total=total, items=items)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    if not job.seen:
        job.seen = True
        session.commit()
    return job


@router.patch("/{job_id}/status", response_model=JobOut)
def update_status(
    job_id: str, payload: StatusUpdate, session: Session = Depends(get_session)
):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Statut invalide : {payload.status}")
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    job.status = payload.status
    session.commit()
    session.refresh(job)
    return job


@router.patch("/{job_id}/notes", response_model=JobOut)
def update_notes(
    job_id: str, payload: NotesUpdate, session: Session = Depends(get_session)
):
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    job.notes = payload.notes
    session.commit()
    session.refresh(job)
    return job


@router.post("/trigger-scrape")
def trigger_scrape(background_tasks: BackgroundTasks):
    from ...pipeline import run

    background_tasks.add_task(run)
    return {"status": "started"}
