from sqlalchemy import or_

from .ai.heuristic import heuristic_score
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
    block = settings.title_block_list
    new: list[Job] = []
    excluded = 0
    with SessionLocal() as session:
        seen_ids: set[str] = set()
        for rj in raw_jobs:
            if should_exclude_title(rj.title, exclude, keep, block):
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
                # Score heuristique immédiat (gratuit) → liste classée dès l'import,
                # et priorité de passage Gemini par pertinence.
                score_heuristic=heuristic_score(rj.title, rj.description),
            )
            session.add(job)
            new.append(job)
        session.commit()
    if excluded:
        print(f"[store] {excluded} offres écartées (titre senior, hors signal stage)")
    return new


def _backfill_descriptions() -> None:
    """Récupère les descriptions LinkedIn manquantes (les plus récentes d'abord).

    L'enrichissement au scrape se faisait 429 trop vite (budget gaspillé sur des
    doublons). Ici on cible UNIQUEMENT les offres LinkedIn sans description, on espace
    les requêtes et on s'arrête sur 429 persistant — le reste se complète au run suivant.
    Une offre déjà taguée SANS description est réinitialisée (score + fiche) pour être
    re-taguée sur du contenu réel (sinon la fiche IA reste « inventée » à partir du titre).
    """
    if not settings.linkedin_description_backfill:
        return
    import random
    import time

    import httpx

    from .scraper.sources.linkedin import (
        fetch_linkedin_description,
        linkedin_headers,
        linkedin_job_id_from_url,
    )

    filled = 0
    consecutive_429 = 0
    with SessionLocal() as session:
        jobs = (
            session.query(Job)
            .filter(
                Job.source == "linkedin",
                or_(Job.description.is_(None), Job.description == ""),
            )
            .order_by(Job.scraped_at.desc())
            .limit(settings.linkedin_backfill_max)
            .all()
        )
        if not jobs:
            return
        print(f"[backfill] {len(jobs)} offres LinkedIn sans description")
        with httpx.Client(
            timeout=settings.request_timeout,
            headers=linkedin_headers(settings),
            follow_redirects=True,
        ) as client:
            for job in jobs:
                jid = linkedin_job_id_from_url(job.url)
                if not jid:
                    continue
                try:
                    desc = fetch_linkedin_description(client, jid)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 429:
                        consecutive_429 += 1
                        if consecutive_429 >= 3:
                            print(f"[backfill] 429 LinkedIn persistant après {filled} — on arrête")
                            break
                        time.sleep(20)
                        continue
                    continue
                except Exception:
                    continue
                consecutive_429 = 0
                if desc:
                    job.description = desc
                    # description réelle → recalcul du score heuristique (meilleur signal)
                    job.score_heuristic = heuristic_score(job.title, desc)
                    # déjà taguée sans description → re-tag propre sur contenu réel
                    if job.score_ai is not None:
                        job.score_ai = None
                        job.details_ai = None
                    filled += 1
                    session.commit()
                time.sleep(random.uniform(1.2, 2.2))  # jitter anti-429
    print(f"[backfill] {filled} descriptions LinkedIn récupérées")


def _backfill_heuristic() -> None:
    """Calcule le score heuristique des offres qui n'en ont pas encore (gratuit, local).
    Couvre les offres importées avant l'introduction du scoring à deux étages."""
    with SessionLocal() as session:
        jobs = session.query(Job).filter(Job.score_heuristic.is_(None)).all()
        if not jobs:
            return
        for job in jobs:
            job.score_heuristic = heuristic_score(job.title, job.description)
        session.commit()
        print(f"[heuristic] {len(jobs)} offres scorées localement")


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
    _backfill_descriptions()
    _backfill_heuristic()
    _tag_new()
    _extract_remaining()
    _notify(new_ids)
    _notify_follow_ups()
    return new
