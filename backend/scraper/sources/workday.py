import httpx

from ..base import BaseScraper, RawJob, is_france, strip_html


class WorkdayScraper(BaseScraper):
    """ATS Workday — API CXS publique (POST JSON), sans clé.

    De nombreux grands groupes sport l'utilisent (ex. Deckers -> HOKA/UGG, New Balance).
    Chaque « site » se décrit par un triplet `tenant:datacenter:site`
    (ex. "deckers:wd5:deckers"), configurable via `workday_sites` (séparés par des virgules).

    On pré-filtre côté serveur avec searchText="France" puis on confirme la localisation,
    et on récupère la description complète via l'endpoint détail (externalPath).
    """

    name = "workday"
    PAGE_LIMIT = 20

    @property
    def sites(self) -> list[tuple[str, str, str]]:
        out: list[tuple[str, str, str]] = []
        for raw in (self.settings.workday_sites or "").split(","):
            parts = [p.strip() for p in raw.split(":")]
            if len(parts) == 3 and all(parts):
                out.append((parts[0], parts[1], parts[2]))
        return out

    def fetch(self) -> list[RawJob]:
        out: list[RawJob] = []
        with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
            for tenant, dc, site in self.sites:
                try:
                    out.extend(self._fetch_site(client, tenant, dc, site))
                except Exception as exc:  # un site en échec ne bloque pas les autres
                    print(f"[workday:{tenant}] ERREUR: {exc!r}")
        return out

    @property
    def _headers(self) -> dict[str, str]:
        return {**self.headers, "Accept": "application/json", "Content-Type": "application/json"}

    def _fetch_site(self, client, tenant: str, dc: str, site: str) -> list[RawJob]:
        host = f"https://{tenant}.{dc}.myworkdayjobs.com"
        jobs_url = f"{host}/wday/cxs/{tenant}/{site}/jobs"
        jobs: list[RawJob] = []
        fetched_desc = 0
        offset = 0
        while True:
            resp = client.post(
                jobs_url,
                json={"limit": self.PAGE_LIMIT, "offset": offset, "searchText": "France", "appliedFacets": {}},
            )
            resp.raise_for_status()
            data = resp.json()
            postings = data.get("jobPostings", [])
            if not postings:
                break
            for p in postings:
                location = p.get("locationsText", "")
                if not is_france(location):
                    continue
                path = p.get("externalPath", "")
                url, description = "", ""
                if fetched_desc < self.settings.workday_max_descriptions:
                    url, description = self._fetch_detail(client, tenant, dc, site, path)
                    fetched_desc += 1
                jobs.append(
                    RawJob(
                        title=p.get("title", ""),
                        company=tenant.capitalize(),
                        source="workday",
                        url=url or f"{host}/{site}{path}",
                        location=location,
                        description=description,
                        source_id=path or None,
                    )
                )
            offset += self.PAGE_LIMIT
            if offset >= data.get("total", 0):
                break
        return jobs

    def _fetch_detail(self, client, tenant: str, dc: str, site: str, path: str) -> tuple[str, str]:
        if not path:
            return "", ""
        try:
            host = f"https://{tenant}.{dc}.myworkdayjobs.com"
            resp = client.get(f"{host}/wday/cxs/{tenant}/{site}{path}")
            resp.raise_for_status()
            info = resp.json().get("jobPostingInfo", {})
            return info.get("externalUrl", ""), strip_html(info.get("jobDescription", ""))
        except Exception:
            return "", ""
