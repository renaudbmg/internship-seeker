from __future__ import annotations

import json
import re
import time

import httpx
from bs4 import BeautifulSoup

from ..base import BaseScraper, RawJob

# WTTJ utilise Algolia pour son moteur de recherche public.
# L'App ID est stable ; la search-only API key est injectée dans le HTML (Next.js __NEXT_DATA__
# ou balise <script>) et peut être extraite à chaque run sans authentification partenaire.
_ALGOLIA_APP_ID = "RQFG0FUOMC"
_ALGOLIA_INDEX = "wttj_production_jobs_fr"
_ALGOLIA_URL = f"https://{_ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/{_ALGOLIA_INDEX}/query"
_JOBS_PAGE = "https://www.welcometothejungle.com/fr/jobs"

# Patterns pour retrouver la clé Algolia dans le HTML ou les bundles JS.
# La clé est une chaîne alphanumérique (pas forcément hex pur) de 32 caractères,
# souvent trouvée dans les chunks Next.js près de l'App ID "RQFG0FUOMC".
_KEY_PATTERNS = [
    # Format JSON/objet : "algoliaApiKey":"xxxxx"
    re.compile(r'"(?:algoliaApiKey|algolia_api_key|searchApiKey|apiKey)"\s*[,:]\s*"([A-Za-z0-9]{20,40})"'),
    # Format JS minifié : apiKey:"xxxxx" ou apiKey:'xxxxx'
    re.compile(r'apiKey["\s:\']+([A-Za-z0-9]{20,40})["\s\']+'),
    # Proche de l'App ID (dans les bundles JS minifiés)
    re.compile(r'RQFG0FUOMC.{0,100}?([A-Za-z0-9]{32})'),
    re.compile(r'([A-Za-z0-9]{32}).{0,100}?RQFG0FUOMC'),
]
_BASE_URL = "https://www.welcometothejungle.com"


class WTTJScraper(BaseScraper):
    """Welcome to the Jungle — recherche via l'API Algolia publique (powers leur frontend).

    La clé de recherche Algolia est une search-only key publique intégrée dans leur page.
    Elle est extraite dynamiquement à chaque run pour résister aux rotations de clé.
    """

    name = "wttj"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            **self.headers,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "fr-FR,fr;q=0.9",
        }

    def fetch(self) -> list[RawJob]:
        with httpx.Client(timeout=self.timeout, headers=self._headers, follow_redirects=True) as client:
            api_key = self._get_algolia_key(client)
            if not api_key:
                print("[wttj] clé Algolia introuvable — source ignorée")
                return []

            jobs: dict[str, RawJob] = {}
            for keyword in self.settings.keyword_list:
                for job in self._search(client, api_key, keyword):
                    jobs.setdefault(job.source_id, job)
                time.sleep(0.5)

        return list(jobs.values())

    def _get_algolia_key(self, client: httpx.Client) -> str | None:
        try:
            resp = client.get(_JOBS_PAGE)
            resp.raise_for_status()
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

            # 1. __NEXT_DATA__ : props injectées côté serveur
            script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
            if script_tag and script_tag.string:
                try:
                    key = self._dig_algolia_key(json.loads(script_tag.string))
                    if key:
                        return key
                except (json.JSONDecodeError, ValueError):
                    pass

            # 2. Regex dans le HTML inline (variables window.*, balises <script>)
            for pattern in _KEY_PATTERNS:
                m = pattern.search(html)
                if m and m.group(1) != _ALGOLIA_APP_ID:
                    return m.group(1)

            # 3. Bundles JS Next.js : la clé Algolia est souvent dans un chunk _app ou pages.
            # On récupère les URLs de script, on cherche dans ceux qui contiennent l'App ID.
            script_urls = [
                tag["src"] for tag in soup.find_all("script", src=True)
                if "_next/static" in (tag.get("src") or "")
            ]
            for src in script_urls[:10]:
                url = src if src.startswith("http") else _BASE_URL + src
                try:
                    bundle = client.get(url, timeout=15).text
                    if _ALGOLIA_APP_ID not in bundle:
                        continue  # ce chunk ne contient pas l'App ID → skip
                    for pattern in _KEY_PATTERNS:
                        m = pattern.search(bundle)
                        if m and m.group(1) != _ALGOLIA_APP_ID:
                            return m.group(1)
                except Exception:
                    continue

        except Exception as exc:
            print(f"[wttj] erreur extraction clé Algolia: {exc!r}")
        return None

    @staticmethod
    def _dig_algolia_key(obj, depth: int = 0) -> str | None:
        """Parcourt récursivement le JSON Next.js pour trouver une clé Algolia."""
        if depth > 8:
            return None
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.lower() in ("algoliaApiKey", "algolia_api_key", "searchApiKey", "searchapikey"):
                    if isinstance(v, str) and len(v) == 32:
                        return v
                result = WTTJScraper._dig_algolia_key(v, depth + 1)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj[:20]:  # évite les listes géantes
                result = WTTJScraper._dig_algolia_key(item, depth + 1)
                if result:
                    return result
        return None

    def _search(self, client: httpx.Client, api_key: str, keyword: str) -> list[RawJob]:
        headers = {
            **self._headers,
            "X-Algolia-Application-Id": _ALGOLIA_APP_ID,
            "X-Algolia-API-Key": api_key,
            "Content-Type": "application/json",
        }
        body = {
            "query": keyword,
            "filters": "contract_type:internship AND country_code:FR",
            "hitsPerPage": self.settings.wttj_max_per_keyword,
            "attributesToRetrieve": [
                "name",
                "slug",
                "organization",
                "contract_type",
                "office_city",
                "office_country_code",
                "profile",
                "reference",
            ],
        }
        try:
            resp = client.post(_ALGOLIA_URL, json=body, headers=headers)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            jobs = [self._parse_hit(h) for h in hits if h.get("name")]
            print(f"[wttj] {len(jobs)} offres pour « {keyword} »")
            return jobs
        except Exception as exc:
            print(f"[wttj] erreur recherche « {keyword} »: {exc!r}")
            return []

    @staticmethod
    def _parse_hit(hit: dict) -> RawJob:
        org = hit.get("organization") or {}
        org_slug = org.get("slug", "")
        job_slug = hit.get("slug", "")
        ref = hit.get("reference") or hit.get("objectID", "")
        city = hit.get("office_city", "")
        location = f"{city}, France" if city else "France"
        url = (
            f"https://www.welcometothejungle.com/fr/companies/{org_slug}/jobs/{job_slug}"
            if org_slug and job_slug
            else ""
        )
        return RawJob(
            title=hit.get("name", ""),
            company=org.get("name", ""),
            source="wttj",
            url=url,
            location=location,
            description=(hit.get("profile") or "")[:4000],
            source_id=str(ref) if ref else job_slug,
        )
