import time

import httpx
from bs4 import BeautifulSoup

from ..base import BaseScraper, RawJob, title_has_excluded_term


class LinkedInScraper(BaseScraper):
    """LinkedIn Jobs via l'endpoint public « guest » (non officiel, sans connexion).

    C'est le même endpoint que le site utilise pour les visiteurs non connectés.
    Limites : pas d'API officielle, sujet au rate-limiting (429) si on l'interroge
    trop souvent. On reste donc volontairement modeste en volume et tolérant aux
    échecs (une page ou une description qui échoue n'interrompt pas le run).
    """

    name = "linkedin"
    _excluded = 0  # compteur de titres écartés (réinitialisé dans fetch)
    SEARCH_URL = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    )
    DESC_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    PAGE_SIZE = 10  # l'endpoint renvoie ~10 cartes par appel

    @property
    def headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.settings.user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        }

    def fetch(self) -> list[RawJob]:
        jobs: dict[str, RawJob] = {}
        self._excluded = 0  # compteur de titres rejetés (postes senior)
        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            for keyword in self.settings.keyword_list:
                self._search_keyword(client, keyword, jobs)

            if self.settings.linkedin_fetch_descriptions:
                self._enrich_descriptions(client, list(jobs.values()))

        if self._excluded:
            print(f"[linkedin] {self._excluded} offres écartées (titre senior/hors stage)")
        return list(jobs.values())

    def _search_keyword(
        self, client: httpx.Client, keyword: str, jobs: dict[str, RawJob]
    ) -> None:
        for start in range(0, self.settings.linkedin_max_per_keyword, self.PAGE_SIZE):
            params = {
                "keywords": keyword,
                "location": self.settings.location,
                "start": start,
            }
            if self.settings.linkedin_experience_level:
                params["f_E"] = self.settings.linkedin_experience_level
            try:
                resp = client.get(self.SEARCH_URL, params=params)
                if resp.status_code == 429:
                    print(f"[linkedin] 429 rate-limit sur « {keyword} », on arrête la pagination")
                    return
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                print(f"[linkedin] échec recherche « {keyword} » start={start}: {exc!r}")
                return

            cards = self._parse_cards(resp.text)
            if not cards:
                return
            for card in cards:
                jobs.setdefault(card.source_id, card)
            time.sleep(0.4)

    def _parse_cards(self, html: str) -> list[RawJob]:
        soup = BeautifulSoup(html, "html.parser")
        exclude = self.settings.linkedin_title_exclude_list
        out: list[RawJob] = []
        for card in soup.select("div.base-card"):
            urn = card.get("data-entity-urn", "")
            job_id = urn.split(":")[-1] if urn else ""
            if not job_id:
                continue
            title_el = card.select_one("h3.base-search-card__title")
            title = title_el.get_text(strip=True) if title_el else ""
            # Filtre client : on écarte les titres senior AVANT stockage/scoring,
            # le tag f_E de LinkedIn laissant passer des postes hors stage.
            if title_has_excluded_term(title, exclude):
                self._excluded += 1
                continue
            company_el = card.select_one("h4.base-search-card__subtitle")
            location_el = card.select_one("span.job-search-card__location")
            link_el = card.select_one("a.base-card__full-link")
            url = link_el["href"].split("?")[0] if link_el and link_el.has_attr("href") else ""
            out.append(
                RawJob(
                    title=title,
                    company=company_el.get_text(strip=True) if company_el else "",
                    source="linkedin",
                    url=url,
                    location=location_el.get_text(strip=True) if location_el else "",
                    source_id=job_id,
                    logo_url=self._extract_logo(card),
                )
            )
        return out

    @staticmethod
    def _extract_logo(card) -> str | None:
        """Logo entreprise des cartes guest LinkedIn. L'image est chargée en lazy :
        l'URL réelle est dans data-delayed-url (parfois data-ghost-url), src étant un
        placeholder transparent. On filtre les data: URIs."""
        img = card.select_one("img")
        if not img:
            return None
        for attr in ("data-delayed-url", "data-ghost-url", "src"):
            val = img.get(attr)
            if val and val.startswith("http"):
                return val
        return None

    def _enrich_descriptions(self, client: httpx.Client, cards: list[RawJob]) -> None:
        for card in cards[: self.settings.linkedin_max_descriptions]:
            try:
                resp = client.get(self.DESC_URL.format(job_id=card.source_id))
                if resp.status_code == 429:
                    print("[linkedin] 429 rate-limit sur les descriptions, on arrête l'enrichissement")
                    return
                resp.raise_for_status()
            except httpx.HTTPError:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            markup = soup.select_one("div.show-more-less-html__markup")
            if markup:
                card.description = markup.get_text(" ", strip=True)
            time.sleep(0.4)
