from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...db.models import Job
from ..deps import get_session
from ..schemas import (
    HiddenUpdate,
    JobListOut,
    JobOut,
    NotesUpdate,
    StatusUpdate,
    TrackingUpdate,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])

VALID_STATUSES = {"to_review", "interested", "applied", "rejected"}
VALID_RESPONSES = {"pending", "positive", "negative", "ghosted"}


@router.get("", response_model=JobListOut)
def list_jobs(
    session: Session = Depends(get_session),
    source: str | None = None,
    status: str | None = None,
    score_min: int | None = None,
    search: str | None = None,
    hidden: bool = False,  # False = annonces actives ; True = corbeille (archives)
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Job)
    # Par défaut on n'affiche que les annonces non masquées ; hidden=true = la corbeille.
    if hidden:
        stmt = stmt.where(Job.hidden.is_(True))
    else:
        stmt = stmt.where(Job.hidden.isnot(True))
    if source:
        stmt = stmt.where(Job.source == source)
    if status:
        stmt = stmt.where(Job.status == status)
    # Score effectif = score IA si présent, sinon score heuristique (provisoire).
    effective_score = func.coalesce(Job.score_ai, Job.score_heuristic)
    if score_min is not None:
        stmt = stmt.where(effective_score >= score_min)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.description.ilike(pattern),
            )
        )

    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    # Tri par score effectif décroissant (IA prioritaire, heuristique en repli), puis récence.
    stmt = stmt.order_by(effective_score.is_(None), effective_score.desc(), Job.scraped_at.desc())
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
    # Premier passage à « postulé » : on date la candidature et on initialise le suivi.
    if payload.status == "applied" and job.applied_at is None:
        job.applied_at = datetime.now(UTC)
        if job.response is None:
            job.response = "pending"
    session.commit()
    session.refresh(job)
    return job


@router.patch("/{job_id}/tracking", response_model=JobOut)
def update_tracking(
    job_id: str, payload: TrackingUpdate, session: Session = Depends(get_session)
):
    if payload.response is not None and payload.response not in VALID_RESPONSES:
        raise HTTPException(status_code=422, detail=f"Réponse invalide : {payload.response}")
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    job.follow_up_at = payload.follow_up_at
    job.response = payload.response
    session.commit()
    session.refresh(job)
    return job


@router.patch("/{job_id}/hidden", response_model=JobOut)
def update_hidden(
    job_id: str, payload: HiddenUpdate, session: Session = Depends(get_session)
):
    """Masque (archive) ou restaure une annonce. L'annonce reste en base : la dédup
    empêche sa ré-import au prochain scrape, donc pas de re-scoring Gemini."""
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    job.hidden = payload.hidden
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
