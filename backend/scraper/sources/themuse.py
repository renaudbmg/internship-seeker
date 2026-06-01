import httpx

from ..base import BaseScraper, RawJob, strip_html


class TheMuseScraper(BaseScraper):
    """Source gratuite sans clé. Sert de socle fonctionnel immédiat.

    L'API The Muse filtre par catégorie/localisation (pas de plein texte),
    on récupère donc les catégories Data et on laisse le scoring IA (Sprint 2) trier.
    """

    name = "themuse"
    BASE = "https://www.themuse.com/api/public/jobs"
    CATEGORIES = ["Data Science", "Data and Analytics"]
    MAX_PAGES = 2

    def fetch(self) -> list[RawJob]:
        out: list[RawJob] = []
        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            for page in range(self.MAX_PAGES):
                params: list[tuple[str, str]] = [("page", str(page))]
                params += [("category", c) for c in self.CATEGORIES]
                if self.settings.themuse_api_key:
                    params.append(("api_key", self.settings.themuse_api_key))

                resp = client.get(self.BASE, params=params)
                resp.raise_for_status()
                results = resp.json().get("results", [])
                if not results:
                    break
                for item in results:
                    out.append(self._parse(item))
        return out

    @staticmethod
    def _parse(item: dict) -> RawJob:
        locations = item.get("locations") or []
        location = ", ".join(loc.get("name", "") for loc in locations) or "N/A"
        company = (item.get("company") or {}).get("name", "")
        url = (item.get("refs") or {}).get("landing_page", "")
        return RawJob(
            title=item.get("name", ""),
            company=company,
            source="themuse",
            url=url,
            location=location,
            description=strip_html(item.get("contents", "")),
        )
