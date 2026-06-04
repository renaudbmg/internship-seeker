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
    unseen: bool = False,  # True = uniquement les offres jamais ouvertes (nouveautés)
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    stmt = select(Job)
    # Par défaut on n'affiche que les annonces non masquées ; hidden=true = la corbeille.
    if hidden:
        stmt = stmt.where(Job.hidden.is_(True))
    else:
        stmt = stmt.where(Job.hidden.isnot(True))
    if unseen:
        stmt = stmt.where(Job.seen.isnot(True))
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


@router.get("/export.csv")
def export_csv(session: Session = Depends(get_session)):
    """Exporte les candidatures (offres postulées) en CSV pour suivi externe."""
    import csv
    import io

    from fastapi.responses import Response

    jobs = (
        session.execute(
            select(Job)
            .where(or_(Job.status == "applied", Job.applied_at.isnot(None)))
            .order_by(Job.applied_at.desc())
        )
        .scalars()
        .all()
    )

    def _fmt(dt):
        return dt.strftime("%Y-%m-%d") if dt else ""

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Titre", "Entreprise", "Lieu", "Score", "Date candidature",
        "Relance", "Réponse", "Statut", "URL", "Notes",
    ])
    for j in jobs:
        score = j.score_ai if j.score_ai is not None else j.score_heuristic
        writer.writerow([
            j.title, j.company, j.location or "", score if score is not None else "",
            _fmt(j.applied_at), _fmt(j.follow_up_at), j.response or "",
            j.status, j.url, (j.notes or "").replace("\n", " "),
        ])

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=candidatures.csv"},
    )


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
