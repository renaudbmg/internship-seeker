import httpx

from ..base import BaseScraper, RawJob, is_france, strip_html


class SmartRecruitersScraper(BaseScraper):
    """ATS SmartRecruiters — API publique sans clé.

    De nombreuses marques sport y publient leurs offres (ex. Salomon / Amer Sports).
    Configurable via `smartrecruiters_companies` (liste d'identifiants séparés par des
    virgules, ex. "Salomon"). On filtre côté France et on récupère la description
    complète pour alimenter le scoring IA.
    """

    name = "smartrecruiters"
    BASE = "https://api.smartrecruiters.com/v1/companies"
    PAGE_LIMIT = 100
    MAX_DESCRIPTIONS = 40  # garde-fou anti rate-limit (1 requête détail par offre FR)

    @property
    def companies(self) -> list[str]:
        raw = self.settings.smartrecruiters_companies or ""
        return [c.strip() for c in raw.split(",") if c.strip()]

    def fetch(self) -> list[RawJob]:
        out: list[RawJob] = []
        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            for company in self.companies:
                try:
                    out.extend(self._fetch_company(client, company))
                except Exception as exc:  # une marque en échec ne bloque pas les autres
                    print(f"[smartrecruiters:{company}] ERREUR: {exc!r}")
        return out

    def _fetch_company(self, client: httpx.Client, company: str) -> list[RawJob]:
        jobs: list[RawJob] = []
        offset = 0
        fetched_desc = 0
        while True:
            resp = client.get(
                f"{self.BASE}/{company}/postings",
                params={"limit": self.PAGE_LIMIT, "offset": offset},
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("content", [])
            if not content:
                break
            for item in content:
                loc = item.get("location") or {}
                if not is_france(loc.get("fullLocation"), loc.get("country")):
                    continue
                description = ""
                if fetched_desc < self.MAX_DESCRIPTIONS:
                    description = self._fetch_description(client, company, item.get("id", ""))
                    fetched_desc += 1
                jobs.append(self._parse(company, item, description))
            offset += self.PAGE_LIMIT
            if offset >= data.get("totalFound", 0):
                break
        return jobs

    def _fetch_description(self, client: httpx.Client, company: str, posting_id: str) -> str:
        if not posting_id:
            return ""
        try:
            resp = client.get(f"{self.BASE}/{company}/postings/{posting_id}")
            resp.raise_for_status()
            sections = (resp.json().get("jobAd") or {}).get("sections") or {}
            parts = [
                (sections.get(key) or {}).get("text", "")
                for key in ("jobDescription", "qualifications", "additionalInformation")
            ]
            return strip_html(" ".join(p for p in parts if p))
        except Exception:
            return ""

    @staticmethod
    def _parse(company: str, item: dict, description: str) -> RawJob:
        loc = item.get("location") or {}
        location = loc.get("fullLocation") or loc.get("city") or "France"
        posting_id = item.get("id", "")
        return RawJob(
            title=item.get("name", ""),
            company=(item.get("company") or {}).get("name") or company,
            source="smartrecruiters",
            url=f"https://jobs.smartrecruiters.com/{company}/{posting_id}",
            location=location,
            description=description,
            source_id=posting_id or None,
        )
