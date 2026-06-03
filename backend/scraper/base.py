from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RawJob:
    title: str
    company: str
    source: str
    url: str
    location: str = ""
    description: str = ""
    # Identifiant stable fourni par la source (ex: jobId LinkedIn) — privilégié pour la dédup.
    source_id: str | None = None
    # URL du logo de l'entreprise quand la source la fournit (LinkedIn surtout) ; sinon None
    # → le front affiche un repli initiales colorées.
    logo_url: str | None = None

    def job_id(self) -> str:
        if self.source_id:
            raw = f"{self.source.strip().lower()}|{self.source_id.strip()}"
        else:
            raw = f"{self.title.strip().lower()}|{self.company.strip().lower()}|{self.source.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    cleaned = _TAG_RE.sub(" ", text).replace("&nbsp;", " ")
    return _WS_RE.sub(" ", cleaned).strip()


# Indices de localisation France pour filtrer les ATS internationaux (SmartRecruiters,
# Greenhouse…) qui renvoient des offres monde entier. On garde France + télétravail FR.
_FR_HINTS = (
    "france",
    "paris",
    "lyon",
    "annecy",
    "lille",
    "marseille",
    "bordeaux",
    "nantes",
    "toulouse",
    "strasbourg",
    "grenoble",
    "voiron",
    "nice",
    "rennes",
    "montpellier",
    "metz",
    "nancy",
)


def title_matches_any(title: str | None, terms: list[str]) -> bool:
    """True si le titre contient un des termes (mot entier, casse ignorée).

    Correspondance par frontière de mot : "cdi" ne matche PAS "Cdiscount", mais matche
    "Stage CDI". Gère les accents (é, è… sont des caractères de mot en regex Unicode).
    """
    if not title:
        return False
    low = title.lower()
    for term in terms:
        t = term.strip().lower()
        if not t:
            continue
        if re.search(rf"(?<!\w){re.escape(t)}(?!\w)", low):
            return True
    return False


def should_exclude_title(
    title: str | None, exclude: list[str], keep: list[str]
) -> bool:
    """True si le titre doit être écarté.

    Un signal positif (stage, alternance, PFE…) l'emporte : une offre dont le titre
    porte un de ces termes est conservée même si elle contient un terme d'exclusion
    (ex. « Stage Responsable événementiel » → gardée). Sinon, on écarte dès qu'un
    terme d'exclusion senior est présent (ex. « Responsable événementiel » → écartée).
    """
    if title_matches_any(title, keep):
        return False
    return title_matches_any(title, exclude)


# Rétro-compat : ancien nom (exclusion simple sans signal positif).
def title_has_excluded_term(title: str | None, terms: list[str]) -> bool:
    return title_matches_any(title, terms)


def is_france(location_text: str | None, country_code: str | None = None) -> bool:
    """True si l'offre est localisée en France (code pays 'fr' ou ville/France dans le texte)."""
    if country_code and country_code.strip().lower() == "fr":
        return True
    text = (location_text or "").lower()
    return any(hint in text for hint in _FR_HINTS)


class BaseScraper(ABC):
    name: str = "base"

    def __init__(self, settings):
        self.settings = settings

    @property
    def timeout(self) -> float:
        return self.settings.request_timeout

    @property
    def headers(self) -> dict[str, str]:
        return {"User-Agent": self.settings.user_agent}

    @abstractmethod
    def fetch(self) -> list[RawJob]:
        """Récupère les offres de la source. Lève une exception en cas d'échec."""
        raise NotImplementedError
