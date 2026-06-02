import html

import httpx

from ..base import BaseScraper, RawJob, is_france, strip_html


class GreenhouseScraper(BaseScraper):
    """ATS Greenhouse — API publique « job board » sans clé.

    Plusieurs marques running/tech sport y publient (ex. On Running -> board "onrunning").
    Configurable via `greenhouse_boards` (identifiants de board séparés par des virgules).
    `?content=true` renvoie déjà la description : pas de requête détail par offre.
    """

    name = "greenhouse"
    BASE = "https://boards-api.greenhouse.io/v1/boards"

    @property
    def boards(self) -> list[str]:
        raw = self.settings.greenhouse_boards or ""
        return [b.strip() for b in raw.split(",") if b.strip()]

    def fetch(self) -> list[RawJob]:
        out: list[RawJob] = []
        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            for board in self.boards:
                try:
                    out.extend(self._fetch_board(client, board))
                except Exception as exc:  # un board en échec ne bloque pas les autres
                    print(f"[greenhouse:{board}] ERREUR: {exc!r}")
        return out

    def _fetch_board(self, client: httpx.Client, board: str) -> list[RawJob]:
        resp = client.get(f"{self.BASE}/{board}/jobs", params={"content": "true"})
        resp.raise_for_status()
        jobs: list[RawJob] = []
        for item in resp.json().get("jobs", []):
            location = (item.get("location") or {}).get("name", "")
            if not is_france(location):
                continue
            jobs.append(self._parse(board, item, location))
        return jobs

    @staticmethod
    def _parse(board: str, item: dict, location: str) -> RawJob:
        return RawJob(
            title=item.get("title", ""),
            company=item.get("company_name") or board,
            source="greenhouse",
            url=item.get("absolute_url", ""),
            location=location or "France",
            description=strip_html(html.unescape(item.get("content", "") or "")),
            source_id=str(item.get("id")) if item.get("id") else None,
        )
