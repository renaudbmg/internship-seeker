from __future__ import annotations

import json
import time

from ..config import settings
from ..db.database import SessionLocal, init_db
from ..db.models import Job

USER_PROFILE = """\
Étudiant ingénieur civil des Mines de Nancy, spécialisation aide à la décision / data analytics.
Compétences : Python, SQL, BigQuery, dbt, Looker Studio, ETL, LLM, Power BI.
Langues : Français (natif), Anglais C1, Espagnol B2.
Expériences : Data Analyst chez papernest (Barcelone), Consultant Exiom Partners (Paris), VP BDE Mines Nancy.
Passion sport : ex vice-champion de France de hockey sur glace, cycliste (VTT + route), coureur.
Recherche : PFE / stage 6 mois, début mars 2026, en France, secteur sport / événementiel sportif / équipementier sport.
"""

PROMPT_TEMPLATE = """\
Tu évalues une offre d'emploi pour ce candidat :
{profile}

Score cette offre de 0 à 100 selon sa pertinence pour ce profil (un PFE/stage data dans
le sport ou l'événementiel sportif, en France, à partir de mars 2026, vaut un score élevé ;
un poste hors data, hors France, ou en CDI senior vaut un score bas).

Offre :
- Titre : {title}
- Entreprise : {company}
- Lieu : {location}
- Description : {description}

Réponds STRICTEMENT en JSON avec ces clés :
{{"score": <entier 0-100>, "summary": "<résumé en 2 phrases max>", "match_reasons": ["<raison>", ...]}}
"""


class ScoringUnavailable(RuntimeError):
    pass


class Scorer:
    def __init__(self):
        if not settings.gemini_api_key:
            raise ScoringUnavailable(
                "GEMINI_API_KEY manquante — scoring désactivé. "
                "Récupère une clé gratuite sur https://aistudio.google.com/app/apikey"
            )
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(
            settings.gemini_model,
            generation_config={"response_mime_type": "application/json"},
        )

    def score(self, job: Job) -> dict:
        prompt = PROMPT_TEMPLATE.format(
            profile=USER_PROFILE,
            title=job.title,
            company=job.company,
            location=job.location,
            description=(job.description or "")[:4000],
        )
        resp = self._model.generate_content(prompt)
        return self._parse(resp.text)

    @staticmethod
    def _parse(text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        data = json.loads(cleaned)
        return {
            "score": int(data.get("score", 0)),
            "summary": str(data.get("summary", "")),
            "match_reasons": data.get("match_reasons", []),
        }


def score_pending(limit: int | None = None) -> int:
    """Score les offres en base dont score_ai est NULL. Renvoie le nombre scoré."""
    init_db()
    scorer = Scorer()  # lève ScoringUnavailable si pas de clé
    scored = 0
    with SessionLocal() as session:
        query = session.query(Job).filter(Job.score_ai.is_(None))
        if limit:
            query = query.limit(limit)
        pending = query.all()
        for job in pending:
            try:
                result = scorer.score(job)
            except Exception as exc:  # une offre qui échoue ne bloque pas les autres
                print(f"[scorer] échec « {job.title[:40]} »: {exc!r}")
                time.sleep(5)  # pause aussi sur erreur pour éviter de surcharger l'API
                continue
            job.score_ai = result["score"]
            job.summary_ai = result["summary"]
            scored += 1
            session.commit()  # commit par offre : un crash en cours de route ne perd rien
            time.sleep(5)  # free tier = 15 req/min → 1 req / 4s minimum
    print(f"[scorer] {scored} offres scorées sur {len(pending)} en attente")
    return scored


if __name__ == "__main__":
    try:
        score_pending()
    except ScoringUnavailable as exc:
        print(exc)
