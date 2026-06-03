from __future__ import annotations

import json
import time

import httpx
from bs4 import BeautifulSoup

from ..base import BaseScraper, RawJob, strip_html

# JobTeaser n'expose pas d'API publique documentée.
# Leur site est rendu côté serveur : les offres sont soit dans le HTML, soit dans
# __NEXT_DATA__ (Next.js). On scrape les deux en cascade.
_BASE_URL = "https://www.jobteaser.com"
_JOBS_URL = "https://www.jobteaser.com/fr/offres-d-emploi"


class JobTeaserScraper(BaseScraper):
    """JobTeaser — scraping HTML du listing public (stages en France).

    JobTeaser cible les étudiants et jeunes diplômés ; beaucoup d'offres PFE/stage
    de marques sport et événementiel non présentes sur LinkedIn.
    """

    name = "jobteaser"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            **self.headers,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "fr-FR,fr;q=0.9",
        }

    def fetch(self) -> list[RawJob]:
        seen: dict[str, RawJob] = {}
        with httpx.Client(
            timeout=self.timeout, headers=self._headers, follow_redirects=True
        ) as client:
            for keyword in self.settings.keyword_list:
                for job in self._fetch_keyword(client, keyword):
                    seen.setdefault(job.source_id or job.url, job)
                time.sleep(0.5)
        return list(seen.values())

    def _fetch_keyword(self, client: httpx.Client, keyword: str) -> list[RawJob]:
        params = {
            "q": keyword,
            "contract_type_codes[]": "internship",
            "country_codes[]": "fr",
            "locale": "fr",
            "per_page": str(self.settings.jobteaser_max_per_keyword),
        }
        try:
            resp = client.get(_JOBS_URL, params=params)
            resp.raise_for_status()
        except Exception as exc:
            print(f"[jobteaser] erreur « {keyword} »: {exc!r}")
            return []

        jobs = self._parse(resp.text)
        print(f"[jobteaser] {len(jobs)} offres pour « {keyword} »")
        return jobs

    def _parse(self, html: str) -> list[RawJob]:
        soup = BeautifulSoup(html, "html.parser")

        # Tentative 1 : données JSON dans __NEXT_DATA__ (Next.js)
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if script and script.string:
            try:
                data = json.loads(script.string)
                offers = self._dig_offers(data)
                if offers:
                    return [self._parse_json_offer(o) for o in offers if o]
            except (json.JSONDecodeError, ValueError):
                pass

        # Tentative 2 : balises JSON-LD (schema.org JobPosting)
        json_ld_jobs = self._parse_json_ld(soup)
        if json_ld_jobs:
            return json_ld_jobs

        # Tentative 3 : HTML fallback — cartes d'offres classiques
        return self._parse_html_cards(soup)

    @staticmethod
    def _dig_offers(obj, depth: int = 0) -> list | None:
        """Cherche la liste d'offres dans le JSON Next.js."""
        if depth > 6:
            return None
        if isinstance(obj, dict):
            for key in ("jobOffers", "job_offers", "offers", "jobs", "results", "items"):
                if key in obj and isinstance(obj[key], list) and obj[key]:
                    return obj[key]
            for v in obj.values():
                result = JobTeaserScraper._dig_offers(v, depth + 1)
                if result:
                    return result
        elif isinstance(obj, list) and obj:
            # Si c'est une liste d'objets avec un champ "title", c'est probablement les offres
            first = obj[0]
            if isinstance(first, dict) and ("title" in first or "name" in first):
                return obj
        return None

    @staticmethod
    def _parse_json_offer(item: dict) -> RawJob | None:
        title = item.get("title") or item.get("name") or ""
        if not title:
            return None
        company_obj = item.get("company") or item.get("organization") or {}
        company = (
            company_obj.get("name")
            if isinstance(company_obj, dict)
            else str(company_obj)
        ) or ""
        location_obj = item.get("location") or item.get("city") or {}
        location = (
            location_obj.get("name") or location_obj.get("label")
            if isinstance(location_obj, dict)
            else str(location_obj)
        ) or "France"
        slug = item.get("slug") or item.get("id") or ""
        url = item.get("url") or item.get("apply_url") or ""
        if not url and slug:
            url = f"{_BASE_URL}/fr/offres-d-emploi/{slug}"
        description = strip_html(item.get("description") or item.get("profile") or "")
        source_id = str(item.get("id") or item.get("reference") or slug)
        return RawJob(
            title=title,
            company=company,
            source="jobteaser",
            url=url,
            location=location,
            description=description[:4000],
            source_id=source_id,
        )

    @staticmethod
    def _parse_json_ld(soup: BeautifulSoup) -> list[RawJob]:
        jobs = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    items = data
                else:
                    items = [data]
                for item in items:
                    if item.get("@type") != "JobPosting":
                        continue
                    company_obj = item.get("hiringOrganization") or {}
                    location_obj = item.get("jobLocation") or {}
                    address = (
                        location_obj.get("address") if isinstance(location_obj, dict) else {}
                    ) or {}
                    city = address.get("addressLocality") or address.get("addressRegion") or "France"
                    source_id = item.get("identifier", {}).get("value") or item.get("url", "").split("/")[-1]
                    jobs.append(RawJob(
                        title=item.get("title", ""),
                        company=company_obj.get("name", "") if isinstance(company_obj, dict) else "",
                        source="jobteaser",
                        url=item.get("url", ""),
                        location=city,
                        description=strip_html(item.get("description", ""))[:4000],
                        source_id=source_id,
                    ))
            except Exception:
                continue
        return jobs

    @staticmethod
    def _parse_html_cards(soup: BeautifulSoup) -> list[RawJob]:
        jobs = []
        selectors = [
            "article[data-testid]",
            "li[data-testid]",
            ".job-card",
            ".offer-card",
            "article.card",
        ]
        cards = []
        for sel in selectors:
            cards = soup.select(sel)
            if cards:
                break

        for card in cards:
            try:
                title_el = card.select_one("h2, h3, [data-testid*='title'], .title")
                if not title_el:
                    continue
                company_el = card.select_one(
                    ".company, .organization, [data-testid*='company'], [data-testid*='organization']"
                )
                location_el = card.select_one(
                    ".location, .city, [data-testid*='location'], [data-testid*='city']"
                )
                link_el = card.select_one("a[href]")
                href = link_el["href"] if link_el else ""
                if href and not href.startswith("http"):
                    href = _BASE_URL + href
                source_id = href.split("/")[-1].split("?")[0] if href else ""
                jobs.append(RawJob(
                    title=title_el.get_text(strip=True),
                    company=company_el.get_text(strip=True) if company_el else "",
                    source="jobteaser",
                    url=href,
                    location=location_el.get_text(strip=True) if location_el else "France",
                    source_id=source_id,
                ))
            except Exception:
                continue
        return jobs
