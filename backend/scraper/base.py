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

    def job_id(self) -> str:
        if self.source_id:
            raw = f"{self.source.strip().lower()}|{self.source_id.strip()}"
        else:
            raw = f"{self.title.strip().lower()}|{self.company.strip().lower()}|{self.source.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    return _TAG_RE.sub(" ", text).replace("&nbsp;", " ").strip()


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
