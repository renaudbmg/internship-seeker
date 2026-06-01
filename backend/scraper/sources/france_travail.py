import httpx

from ..base import BaseScraper, RawJob, strip_html


class FranceTravailScraper(BaseScraper):
    """API officielle « Offres d'emploi v2 » de France Travail (ex-Pôle Emploi).

    Gratuite mais nécessite des credentials (client_id / client_secret) obtenus
    sur https://francetravail.io. Source robuste et exhaustive pour la France,
    pensée pour remplacer le scraping fragile de WTTJ.
    """

    name = "france_travail"
    TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    SCOPE = "api_offresdemploiv2 o2dsoffre"

    def fetch(self) -> list[RawJob]:
        cid = self.settings.france_travail_client_id
        secret = self.settings.france_travail_client_secret
        if not (cid and secret):
            raise RuntimeError(
                "Credentials France Travail manquants "
                "(france_travail_client_id / france_travail_client_secret)."
            )

        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            token = self._get_token(client, cid, secret)
            return self._search(client, token)

    def _get_token(self, client: httpx.Client, cid: str, secret: str) -> str:
        resp = client.post(
            self.TOKEN_URL,
            params={"realm": "/partenaire"},
            data={
                "grant_type": "client_credentials",
                "client_id": cid,
                "client_secret": secret,
                "scope": self.SCOPE,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _search(self, client: httpx.Client, token: str) -> list[RawJob]:
        resp = client.get(
            self.SEARCH_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={
                "motsCles": ",".join(self.settings.keyword_list),
                "range": "0-49",
            },
        )
        if resp.status_code == 204:  # aucune offre
            return []
        resp.raise_for_status()
        return [self._parse(o) for o in resp.json().get("resultats", [])]

    @staticmethod
    def _parse(o: dict) -> RawJob:
        return RawJob(
            title=o.get("intitule", ""),
            company=(o.get("entreprise") or {}).get("nom", "") or "Entreprise non précisée",
            source="france_travail",
            url=(o.get("origineOffre") or {}).get("urlOrigine", ""),
            location=(o.get("lieuTravail") or {}).get("libelle", ""),
            description=strip_html(o.get("description", "")),
        )
