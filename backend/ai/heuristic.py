"""
Scoring heuristique local (gratuit, instantané) — étage 1 du scoring à deux niveaux.

Objectif : donner à CHAQUE offre un score de pertinence provisoire (0-100) sans appel
Gemini, pour que :
  - la liste soit toujours classée et exploitable, même quand le quota Gemini est épuisé ;
  - le tagger Gemini (étage 2, précis mais limité à ~20/jour) traite les offres les plus
    prometteuses EN PREMIER (priorité par score heuristique, pas par date).

Le score est volontairement simple (mots-clés pondérés du profil candidat). Il sert de
proxy de tri, pas de vérité absolue — Gemini reste l'arbitre final quand il passe.
"""

from __future__ import annotations

import re

# Mots-clés data / décisionnel — cœur du profil (ingénieur data analytics).
_DATA = [
    "data", "données", "analyst", "analytics", "analyse", "data engineer",
    "data scientist", "data science", "business analyst", "business intelligence",
    "décisionnel", "decisionnel", "statistique", "machine learning", "ml",
    "python", "sql", "bigquery", "dbt", "looker", "power bi", "powerbi", "tableau",
    "etl", "elt", "dataviz", "reporting", "kpi", "bi",
]

# Signaux stage / alternance — le candidat cherche un PFE / stage 6 mois.
_INTERN = [
    "stage", "stagiaire", "alternance", "alternant", "alternante", "apprenti",
    "apprentissage", "pfe", "intern", "internship", "fin d'études", "fin d'etudes",
]

# Bonus secteur sport / événementiel sportif / équipementier.
_SPORT = [
    "sport", "sportif", "sportive", "équipementier", "equipementier", "outdoor",
    "vélo", "velo", "cyclisme", "running", "ski", "hockey", "fitness", "athletic",
    "athlétique", "événementiel sportif", "evenementiel sportif", "club", "fédération",
]

# Signaux négatifs (postes pas pour un stagiaire ingénieur data).
_NEG = [
    "senior", "confirmé", "confirmée", "expérimenté", "lead", "directeur", "directrice",
    "head of", "principal", "cdi", "vendeur", "vente", "commercial", "manager",
]


def _count(terms: list[str], text: str) -> int:
    """Nombre de termes présents (mot entier, casse ignorée)."""
    n = 0
    for term in terms:
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text):
            n += 1
    return n


def heuristic_score(title: str | None, description: str | None = "") -> int:
    """Score de pertinence 0-100 basé sur les mots-clés du profil. Pur, gratuit, rapide."""
    title_low = (title or "").lower()
    desc_low = (description or "").lower()
    both = f"{title_low} {desc_low}"

    score = 20  # base neutre

    # --- Pertinence data (le plus important) ---
    if _count(_DATA, title_low):
        score += 40  # data dans le titre = très fort signal
    data_in_desc = _count(_DATA, desc_low)
    score += min(data_in_desc, 6) * 4  # densité data dans la description, plafonné +24

    # --- Stage / alternance ---
    if _count(_INTERN, both):
        score += 12

    # --- Bonus sport ---
    if _count(_SPORT, both):
        score += 12

    # --- Signaux négatifs ---
    if _count(_NEG, title_low):
        score -= 30

    return max(0, min(100, score))
