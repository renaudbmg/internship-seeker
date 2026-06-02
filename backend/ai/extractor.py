from __future__ import annotations

import json
import time

from ..config import settings
from ..db.database import SessionLocal, init_db
from ..db.models import Job
from .quota import is_quota_error

# Champs normés extraits pour chaque offre. Scalaires -> "Non précisé" si absent,
# listes -> [] si absent. Pensé pour comparer les offres d'un coup d'œil.
PROMPT_TEMPLATE = """\
Tu analyses une offre d'emploi et tu en extrais des informations structurées.
N'invente rien : si une information n'est pas dans l'offre, mets "Non précisé"
(pour un champ texte) ou une liste vide (pour une liste).

Offre :
- Titre : {title}
- Entreprise : {company}
- Lieu : {location}
- Description : {description}

Réponds STRICTEMENT en JSON avec EXACTEMENT ces clés :
{{
  "type_contrat": "<Stage | Alternance | CDD | CDI | VIE | Freelance | Autre | Non précisé>",
  "duree": "<ex: 6 mois | Non précisé>",
  "date_debut": "<ex: Mars 2026 | Dès que possible | Non précisé>",
  "remuneration": "<ex: 1300 €/mois | Selon profil | Non précisé>",
  "lieu": "<ville ou région, ex: Annecy | Non précisé>",
  "teletravail": "<Présentiel | Hybride | Full remote | Non précisé>",
  "missions": ["<mission courte>", "..."],
  "competences": ["<compétence clé>", "..."],
  "profil": "<niveau d'études / profil recherché, ex: Bac+5 école d'ingénieur | Non précisé>",
  "secteur": "<ex: Sport / Équipementier | Non précisé>"
}}
"""

# Ordre + valeurs par défaut. Garantit un objet complet même si Gemini en oublie.
_FIELDS: dict[str, object] = {
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


class ExtractionUnavailable(RuntimeError):
    pass


class Extractor:
    def __init__(self):
        if not settings.gemini_api_key:
            raise ExtractionUnavailable(
                "GEMINI_API_KEY manquante — extraction désactivée. "
                "Récupère une clé gratuite sur https://aistudio.google.com/app/apikey"
            )
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(
            settings.gemini_model,
            generation_config={"response_mime_type": "application/json"},
        )

    def extract(self, job: Job) -> dict:
        prompt = PROMPT_TEMPLATE.format(
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
        out: dict[str, object] = {}
        for key, default in _FIELDS.items():
            value = data.get(key, default)
            if isinstance(default, list):
                out[key] = value if isinstance(value, list) else []
            else:
                out[key] = str(value) if value is not None else default
        return out


def extract_pending(limit: int | None = None) -> int:
    """Extrait les champs normés des offres dont details_ai est NULL. Renvoie le nombre traité."""
    init_db()
    extractor = Extractor()  # lève ExtractionUnavailable si pas de clé
    done = 0
    with SessionLocal() as session:
        query = session.query(Job).filter(Job.details_ai.is_(None))
        if limit:
            query = query.limit(limit)
        pending = query.all()
        for job in pending:
            try:
                result = extractor.extract(job)
            except Exception as exc:
                if is_quota_error(exc):
                    # quota journalier Gemini épuisé : on stoppe, le reste reste en file
                    print(f"[extractor] quota Gemini atteint après {done} offres — reste en file")
                    break
                # une offre qui échoue (autre cause) ne bloque pas les autres
                print(f"[extractor] échec « {job.title[:40]} »: {exc!r}")
                time.sleep(5)
                continue
            job.details_ai = json.dumps(result, ensure_ascii=False)
            done += 1
            session.commit()  # commit par offre : un crash en cours de route ne perd rien
            time.sleep(5)  # free tier = 15 req/min → 1 req / 4s minimum
        print(f"[extractor] {done} offres enrichies sur {len(pending)} en attente")
    return done


if __name__ == "__main__":
    try:
        extract_pending()
    except ExtractionUnavailable as exc:
        print(exc)
