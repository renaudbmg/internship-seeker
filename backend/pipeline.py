from sqlalchemy import or_

from .config import settings
from .db.database import SessionLocal, init_db
from .db.models import Job
from .scraper.base import RawJob, should_exclude_title
from .scraper.registry import build_scrapers


def _collect() -> list[RawJob]:
    raw: list[RawJob] = []
    for scraper in build_scrapers(settings):
        try:
            jobs = scraper.fetch()
            print(f"[{scraper.name}] {len(jobs)} offres récupérées")
            raw.extend(jobs)
        except Exception as exc:  # une source en échec ne bloque pas les autres
            print(f"[{scraper.name}] ERREUR: {exc!r}")
    return raw


def _store(raw_jobs: list[RawJob]) -> list[Job]:
    """Déduplique par hash d'id et n'insère que les offres jamais vues.

    Filtre aussi les titres senior (toutes sources) AVANT insertion : une offre
    écartée n'est jamais stockée ni scorée, ce qui préserve le quota Gemini.
    """
    exclude = settings.title_exclude_list
    keep = settings.title_keep_list
    new: list[Job] = []
    excluded = 0
    with SessionLocal() as session:
        seen_ids: set[str] = set()
        for rj in raw_jobs:
            if should_exclude_title(rj.title, exclude, keep):
                excluded += 1
                continue
            jid = rj.job_id()
            if jid in seen_ids:
                continue  # doublon au sein du même run
            seen_ids.add(jid)
            existing = session.get(Job, jid)
            if existing is not None:
                if rj.logo_url and not existing.logo_url:
                    existing.logo_url = rj.logo_url
                continue
            job = Job(
                id=jid,
                title=rj.title,
                company=rj.company,
                source=rj.source,
                url=rj.url,
                location=rj.location,
                description=rj.description,
                logo_url=rj.logo_url,
            )
            session.add(job)
            new.append(job)
        session.commit()
    if excluded:
        print(f"[store] {excluded} offres écartées (titre senior, hors signal stage)")
    return new


def _tag_new() -> None:
    """Scoring + extraction combinés en 1 appel Gemini par offre (tagger.py).

    Traite les offres dont score_ai IS NULL. Maximise le quota free tier
    (1 500 RPD, 15 RPM) : sleep 4s entre appels dans tag_pending().
    """
    if not settings.scoring_enabled:
        return
    from .ai.tagger import TaggerUnavailable, tag_pending

    try:
        tag_pending()
    except TaggerUnavailable as exc:
        print(f"[tagger] ignoré : {exc}")


def _extract_remaining() -> None:
    """Backward-compat : extraction seule pour offres déjà scorées sans details_ai."""
    if not settings.extraction_enabled:
        return
    from .ai.extractor import ExtractionUnavailable, extract_pending

    try:
        extract_pending()
    except ExtractionUnavailable as exc:
        print(f"[extractor] ignoré : {exc}")


def _notify(new_ids: list[str]) -> None:
    """Notifie les nouvelles offres via Telegram, en relisant leurs scores frais."""
    if not new_ids:
        return
    from .notifications.telegram import TelegramUnavailable, notify_new_jobs

    with SessionLocal() as session:
        jobs = [j for j in (session.get(Job, jid) for jid in new_ids) if j is not None]
    try:
        notify_new_jobs(jobs)
        print(f"[telegram] {len(jobs)} offres notifiées")
    except TelegramUnavailable as exc:
        print(f"[telegram] ignoré : {exc}")
    except Exception as exc:  # une notif en échec ne doit pas casser le run
        print(f"[telegram] ERREUR: {exc!r}")


def _notify_follow_ups() -> None:
    """Rappelle les relances dues : candidatures postulées dont la date de relance est
    passée et qui n'ont pas encore de réponse définitive."""
    from datetime import datetime, timezone

    from .notifications.telegram import TelegramUnavailable, notify_follow_ups

    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        due = (
            session.query(Job)
            .filter(
                Job.follow_up_at.isnot(None),
                Job.follow_up_at <= now,
                or_(Job.response.is_(None), Job.response == "pending"),
            )
            .order_by(Job.follow_up_at.asc())
            .all()
        )
    if not due:
        return
    try:
        notify_follow_ups(due)
        print(f"[telegram] {len(due)} relance(s) rappelée(s)")
    except TelegramUnavailable as exc:
        print(f"[telegram] relances ignorées : {exc}")
    except Exception as exc:  # une notif en échec ne doit pas casser le run
        print(f"[telegram] ERREUR relances: {exc!r}")


def run() -> list[Job]:
    init_db()
    raw = _collect()
    new = _store(raw)
    new_ids = [j.id for j in new]
    print(f"\n{len(new)} nouvelles offres stockées (sur {len(raw)} récupérées).")
    for job in new[:10]:
        print(f"  • [{job.source}] {job.title} — {job.company} ({job.location})")
    _tag_new()
    _extract_remaining()
    _notify(new_ids)
    _notify_follow_ups()
    return new
