from __future__ import annotations

import json

from ..config import settings
from ..db.database import SessionLocal, init_db
from ..db.models import Job
from .quota import run_quota_loop

USER_PROFILE = """\
Étudiant ingénieur civil des Mines de Nancy, spécialisation aide à la décision / data analytics.
Compétences : Python, SQL, BigQuery, dbt, Looker Studio, ETL, LLM, Power BI.
Langues : Français (natif), Anglais C1, Espagnol B2.
Expériences : Data Analyst chez papernest (Barcelone), Consultant Exiom Partners (Paris), VP BDE Mines Nancy.
Passion sport : ex vice-champion de France de hockey sur glace, cycliste (VTT + route), coureur.
Recherche : PFE / stage 6 mois, début mars 2026, en France, secteur sport / événementiel sportif / équipementier sport.
"""

# Prompt combiné : scoring + extraction en un seul appel Gemini.
# Économise 1 appel par offre vs l'ancienne approche en deux passes séparées.
PROMPT_TEMPLATE = """\
Tu évalues et analyses une offre d'emploi pour ce candidat :
{profile}

Tu dois simultanément :
1. Scorer l'offre de 0 à 100 selon sa pertinence (PFE/stage data dans le sport ou l'événementiel
   sportif, en France, à partir de mars 2026 = score élevé ; hors data, hors France, CDI senior = bas)
2. Extraire les informations structurées de l'offre

Offre :
- Titre : {title}
- Entreprise : {company}
- Lieu : {location}
- Description : {description}

Réponds STRICTEMENT en JSON avec EXACTEMENT ces clés :
{{
  "score": <entier 0-100>,
  "match_reasons": ["<raison>"],
  "type_contrat": "<Stage | Alternance | CDD | CDI | VIE | Freelance | Autre | Non précisé>",
  "duree": "<ex: 6 mois | Non précisé>",
  "date_debut": "<ex: Mars 2026 | Dès que possible | Non précisé>",
  "remuneration": "<ex: 1300 €/mois | Selon profil | Non précisé>",
  "lieu": "<ville ou région, ex: Annecy | Non précisé>",
  "teletravail": "<Présentiel | Hybride | Full remote | Non précisé>",
  "missions": ["<mission courte>"],
  "competences": ["<compétence clé>"],
  "profil": "<niveau d'études / profil recherché, ex: Bac+5 école d'ingénieur | Non précisé>",
  "secteur": "<ex: Sport / Équipementier | Non précisé>"
}}
"""

_EXTRACTION_FIELDS: dict[str, object] = {
    "type_contrat": "Non précisé",
    "duree": "Non précisé",
    "date_debut": "Non précisé",
    "remuneration": "Non précisé",
    "lieu": "Non précisé",
    "teletravail": "Non précisé",
    "missions": [],
    "competences": [],
    "profil": "Non précisé",
    "secteur": "Non précisé",
}


class TaggerUnavailable(RuntimeError):
    pass


class Tagger:
    def __init__(self):
        if not settings.gemini_api_key:
            raise TaggerUnavailable(
                "GEMINI_API_KEY manquante — tagging désactivé. "
                "Récupère une clé gratuite sur https://aistudio.google.com/app/apikey"
            )
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(
            settings.gemini_model,
            generation_config={"response_mime_type": "application/json"},
        )

    def tag(self, job: Job) -> dict:
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

        # Champs scoring
        score = int(data.get("score", 0))
        match_reasons = data.get("match_reasons", [])
        if not isinstance(match_reasons, list):
            match_reasons = []

        # Champs extraction
        details: dict[str, object] = {}
        for key, default in _EXTRACTION_FIELDS.items():
            value = data.get(key, default)
            if isinstance(default, list):
                details[key] = value if isinstance(value, list) else []
            else:
                details[key] = str(value) if value is not None else default

        return {
            "score": score,
            "match_reasons": match_reasons,
            "details": details,
        }


def tag_pending(limit: int | None = None) -> int:
    """Score + extrait les offres dont score_ai est NULL en un seul appel Gemini par offre.

    Délègue le rythme et la gestion des 429 (RPM transitoire vs RPD journalier) à
    run_quota_loop, pour consommer tout le quota du jour. Renvoie le nombre tagué.
    """
    init_db()
    tagger = Tagger()
    with SessionLocal() as session:
        # Les offres les plus récentes d'abord : si le quota ne couvre pas tout le
        # backlog, ce sont les nouvelles offres du jour qui sont taguées en priorité
        # (et donc scorées avant la notification Telegram du matin).
        query = (
            session.query(Job)
            .filter(Job.score_ai.is_(None))
            .order_by(Job.scraped_at.desc())
        )
        if limit:
            query = query.limit(limit)
        pending = query.all()
        print(f"[tagger] {len(pending)} offres à tagger (scoring + extraction)")

        def process(job: Job) -> None:
            result = tagger.tag(job)
            job.score_ai = result["score"]
            job.details_ai = json.dumps(result["details"], ensure_ascii=False)
            session.commit()  # commit par offre : un crash en cours de route ne perd rien

        tagged, _ = run_quota_loop(pending, process, label="tagger")
    print(f"[tagger] {tagged} offres taguées sur {len(pending)} en attente")
    return tagged


if __name__ == "__main__":
    try:
        tag_pending()
    except TaggerUnavailable as exc:
        print(exc)
