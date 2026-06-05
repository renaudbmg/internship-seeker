from __future__ import annotations

import json

from sqlalchemy import func, or_

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
  "remuneration": "<rému EXPLICITEMENT mentionnée dans l'offre, ex: 1300 €/mois | Non précisé>",
  "remuneration_estimee": "<fourchette estimée d'après le type de contrat, le niveau et la ville,
     selon les grilles françaises courantes (ex stage Bac+5 data: 1100-1500 €/mois ;
     alternance: 900-1400 €/mois ; CDI junior data: 35-45 k€/an). TOUJOURS donner une fourchette.>",
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
    "remuneration_estimee": "Non précisé",
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
        self._keys = settings.gemini_key_list
        if not self._keys:
            raise TaggerUnavailable(
                "GEMINI_API_KEY manquante — tagging désactivé. "
                "Récupère une clé gratuite sur https://aistudio.google.com/app/apikey"
            )
        import google.generativeai as genai

        self._genai = genai
        self._key_index = 0
        self._configure()

    def _configure(self) -> None:
        self._genai.configure(api_key=self._keys[self._key_index])
        self._model = self._genai.GenerativeModel(
            settings.gemini_model,
            generation_config={"response_mime_type": "application/json"},
        )

    @property
    def keys_count(self) -> int:
        return len(self._keys)

    def rotate_key(self) -> bool:
        """Passe à la clé suivante (autre compte) quand la courante a épuisé son RPD.
        Renvoie False s'il n'y a plus de clé disponible."""
        if self._key_index + 1 >= len(self._keys):
            return False
        self._key_index += 1
        self._configure()
        print(f"[tagger] bascule sur la clé Gemini #{self._key_index + 1}/{len(self._keys)}")
        return True

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
        # Priorité par score heuristique DÉCROISSANT (les offres les plus prometteuses
        # d'abord), puis par récence. Si le quota Gemini ne couvre pas tout le backlog,
        # ce sont les meilleures offres qui sont taguées en priorité — pas juste les
        # plus récentes. (score_heuristic NULL = traité en dernier via COALESCE.)
        query = (
            session.query(Job)
            .filter(Job.score_ai.is_(None), Job.hidden.isnot(True))
            .order_by(
                func.coalesce(Job.score_heuristic, 0).desc(),
                Job.scraped_at.desc(),
            )
        )
        # Seuil heuristique : on ne gaspille pas Gemini sur les offres peu prometteuses.
        # On garde celles sans score heuristique (NULL) par sécurité.
        floor = settings.gemini_min_heuristic
        if floor > 0:
            query = query.filter(
                or_(Job.score_heuristic.is_(None), Job.score_heuristic >= floor)
            )
        if limit:
            query = query.limit(limit)
        pending = query.all()
        print(
            f"[tagger] {len(pending)} offres à tagger (scoring + extraction) "
            f"— {tagger.keys_count} clé(s) Gemini"
        )

        def process(job: Job) -> None:
            result = tagger.tag(job)
            job.score_ai = result["score"]
            job.details_ai = json.dumps(result["details"], ensure_ascii=False)
            session.commit()  # commit par offre : un crash en cours de route ne perd rien

        # Boucle de quota avec rotation de clés : quand une clé épuise son RPD, on
        # bascule sur la suivante et on reprend les offres restantes (encore non taguées).
        total = 0
        while True:
            remaining = [j for j in pending if j.score_ai is None]
            if not remaining:
                break
            tagged, daily_exhausted = run_quota_loop(remaining, process, label="tagger")
            total += tagged
            if daily_exhausted and tagger.rotate_key():
                continue
            break
    print(f"[tagger] {total} offres taguées sur {len(pending)} en attente")
    return total


if __name__ == "__main__":
    try:
        tag_pending()
    except TaggerUnavailable as exc:
        print(exc)
