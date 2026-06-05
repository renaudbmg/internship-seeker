from __future__ import annotations

import random
import re
import time

import httpx
from bs4 import BeautifulSoup

from ...ai.heuristic import heuristic_score
from ..base import BaseScraper, RawJob, strip_html

_BASE = "https://www.jobteaser.com"
# Le listing JobTeaser n'est pas filtrable par mot-clé (?q= → 403) : on récupère
# tous les contrats étudiants puis on ne garde que les titres data/sport pertinents
# (score heuristique titre ≥ seuil). Évite de noyer la base de bruit généraliste.
_MIN_TITLE_SCORE = 40
_LISTING = f"{_BASE}/fr/job-offers"

# Pool de User-Agents (le 403 JobTeaser est capricieux : on varie + on réessaie).
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]

# UUID en tête de slug : /fr/job-offers/<uuid>-<entreprise>-<titre>
_UUID_RE = re.compile(r"/fr/job-offers/([0-9a-f-]{36})")
# Contrats qu'on garde (stage / alternance / 1er emploi) — JobTeaser est étudiant.
_KEEP_CONTRACT = ("stage", "alternance", "apprentissage", "vie", "graduate", "premier emploi")


class JobTeaserScraper(BaseScraper):
    """JobTeaser — plateforme stage/alternance étudiante (FR).

    La recherche par mot-clé (?q=) renvoie 403, mais le listing général est servi
    en HTML server-rendered. On pagine le listing, on parse les cartes (entreprise,
    titre, contrat, lien), on filtre les contrats stage/alternance, et le pipeline
    applique ensuite le filtrage titre + scoring. Descriptions récupérées sur la
    page détail (limité, avec jitter, tolérant au 403).
    """

    name = "jobteaser"

    def _hdrs(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Referer": _LISTING,
        }

    def fetch(self) -> list[RawJob]:
        jobs: dict[str, RawJob] = {}
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for page in range(1, self.settings.jobteaser_max_pages + 1):
                html = self._get_listing(client, page)
                if not html:
                    continue
                cards = self._parse_cards(html)
                if not cards:
                    break  # plus de résultats
                for card in cards:
                    jobs.setdefault(card.source_id or card.url, card)
                time.sleep(random.uniform(1.0, 2.0))

            # Descriptions (limité, tolérant) pour de meilleures fiches IA.
            self._enrich(client, list(jobs.values()))

        return list(jobs.values())

    def _get_listing(self, client: httpx.Client, page: int, retries: int = 2) -> str | None:
        # page 1 = URL de base (le param ?page=1 renvoie 403) ; page ≥2 = ?page=N.
        url = _LISTING if page == 1 else f"{_LISTING}?page={page}"
        for attempt in range(retries + 1):
            try:
                r = client.get(url, headers=self._hdrs())
                if r.status_code == 403:
                    if attempt < retries:
                        time.sleep(random.uniform(3, 6))
                        continue
                    print(f"[jobteaser] 403 persistant page {page}")
                    return None
                r.raise_for_status()
                return r.text
            except httpx.HTTPError as exc:
                print(f"[jobteaser] échec page {page}: {exc!r}")
                return None
        return None

    def _parse_cards(self, html: str) -> list[RawJob]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[RawJob] = []
        for card in soup.select('[class*="JobAdCard-module"]'):
            link = card.select_one('a[class*="link"][href*="/fr/job-offers/"]')
            if not link:
                continue
            title = link.get_text(strip=True)
            href = link.get("href", "")
            company_el = card.select_one('[class*="companyName"]')
            company = company_el.get_text(strip=True) if company_el else ""
            contract_el = card.select_one('[data-testid="jobad-card-contract"]')
            contract = contract_el.get_text(" ", strip=True).lower() if contract_el else ""

            # On ne garde que stage/alternance/1er emploi (sinon trop de CDI seniors).
            if contract and not any(k in contract for k in _KEEP_CONTRACT):
                continue
            if not title or not href:
                continue
            # Pertinence : titre data/sport uniquement (le listing est généraliste).
            if heuristic_score(title) < _MIN_TITLE_SCORE:
                continue

            m = _UUID_RE.search(href)
            out.append(
                RawJob(
                    title=title,
                    company=company,
                    source="jobteaser",
                    url=_BASE + href if href.startswith("/") else href,
                    location="France",
                    source_id=m.group(1) if m else None,
                )
            )
        return out

    def _enrich(self, client: httpx.Client, cards: list[RawJob]) -> None:
        for card in cards[: self.settings.jobteaser_max_descriptions]:
            try:
                r = client.get(card.url, headers=self._hdrs())
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                body = soup.select_one('[class*="JobAdDescription"], main, article')
                if body:
                    card.description = strip_html(body.get_text(" ", strip=True))[:4000]
            except Exception:
                continue
            time.sleep(random.uniform(1.0, 2.0))
