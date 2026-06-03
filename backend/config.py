from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Recherche
    keywords: str = "data analyst, data engineer, business analyst, sport, événementiel"
    location: str = "France"

    # Source: LinkedIn Jobs via endpoint public « guest » (non officiel)
    linkedin_enabled: bool = True
    linkedin_max_per_keyword: int = 25  # ~10 offres par page
    linkedin_fetch_descriptions: bool = True
    linkedin_max_descriptions: int = 50  # limite anti rate-limit
    # Filtre serveur LinkedIn f_E (niveau d'expérience) : 1=Stage, 2=Débutant,
    # 3=Confirmé, 4=Senior, 5=Directeur, 6=Exécutif. "1,2" = stage + entrée de carrière.
    # → LinkedIn ne renvoie que ces niveaux : pool déjà filtré avant import/scoring.
    linkedin_experience_level: str | None = "1,2"
    # Filtre client : titres rejetés AVANT stockage (le tag f_E de LinkedIn est imparfait
    # et laisse passer des postes senior). Correspondance par mot entier, casse ignorée.
    # NB: "responsable" / "manager" volontairement absents (trop ambigus : un stage peut
    # être « Stage Responsable… »). Ils sont gérés par le signal positif ci-dessous.
    linkedin_title_exclude: str = (
        "senior,confirmé,confirmée,expérimenté,expérimentée,lead,"
        "directeur,directrice,head of,principal,chef de,expert,architecte,cdi,vie,v.i.e"
    )
    # Signaux positifs : si le titre contient un de ces termes, l'offre est CONSERVÉE
    # même si elle matche un terme d'exclusion (« Stage Responsable événementiel » → gardée).
    linkedin_title_keep: str = (
        "stage,stagiaire,intern,internship,alternance,alternant,alternante,"
        "apprenti,apprentie,apprentissage,pfe,fin d'études,fin d'etudes"
    )

    # Source: The Muse (gratuite, sans clé) — socle de secours, désactivé par défaut
    themuse_enabled: bool = False
    themuse_api_key: str | None = None

    # Source: ATS SmartRecruiters (API publique, sans clé). Marques sport (ex. Salomon, Asics).
    # `smartrecruiters_companies` = identifiants séparés par des virgules.
    smartrecruiters_enabled: bool = True
    smartrecruiters_companies: str = "Salomon,Asics"

    # Source: ATS Greenhouse (API publique « job board », sans clé). Ex. On Running.
    # `greenhouse_boards` = identifiants de board séparés par des virgules.
    greenhouse_enabled: bool = True
    greenhouse_boards: str = "onrunning"

    # Source: ATS Workday (API CXS publique). Triplets `tenant:datacenter:site` séparés
    # par des virgules. Ex. Deckers (HOKA/UGG). New Balance dispo : "newbalance:wd1:careers".
    workday_enabled: bool = True
    workday_sites: str = "deckers:wd5:deckers"
    workday_max_descriptions: int = 30

    # Scoring IA + extraction — Gemini Flash (1 appel combiné par offre via tagger.py)
    scoring_enabled: bool = True
    gemini_api_key: str | None = None  # https://aistudio.google.com/app/apikey
    # Limites réelles vérifiées sur aistudio.google.com/rate-limit (free tier) :
    #   gemini-2.5-flash : 5 RPM, 250K TPM, 20 RPD
    # gemini-2.5-flash-lite n'est pas disponible sur ce compte.
    # PACE_SECONDS dans quota.py = 13s (marge confortable sous 5 RPM = 12s min).
    gemini_model: str = "gemini-2.5-flash"
    # Extraction de champs normés — activée via le tagger combiné (même flag).
    # Conservé pour le chemin de backward-compat (offres déjà scorées sans extraction).
    extraction_enabled: bool = True
    # RPD réel = 20. Avec le tagger combiné (1 appel/offre), on tague 20 offres/jour max.
    # ~265 offres en attente → ~13 jours pour tout tagger au rythme actuel.
    gemini_daily_quota: int = 20

    # Source: Welcome to the Jungle (via Algolia public, extrait depuis leur page)
    wttj_enabled: bool = True
    wttj_max_per_keyword: int = 50

    # Source: JobTeaser (scraping HTML) — désactivé : leur site renvoie 404/403 aux scrapers.
    # Leur URL /fr/offres-d-emploi n'existe plus et /fr/job-offers bloque les bots.
    jobteaser_enabled: bool = False
    jobteaser_max_per_keyword: int = 50

    # Notifications Telegram (Sprint 5) — bot API directe
    # 1) parler à @BotFather -> /newbot -> récupérer le token
    # 2) chat_id: parler à son bot puis GET api.telegram.org/bot<token>/getUpdates
    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    dashboard_url: str | None = None  # lien inclus dans le message (front déployé)

    # Stockage
    db_path: str = "backend/db/jobs.db"  # SQLite local (dev / Mac)
    # Turso (libSQL) — base distante persistante pour le déploiement.
    # Si défini, prend le pas sur db_path. URL fournie par `turso db show --url`.
    turso_database_url: str | None = None  # ex: libsql://ma-base-org.turso.io
    turso_auth_token: str | None = None  # `turso db tokens create ma-base`

    # HTTP
    request_timeout: float = 20.0
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )

    @property
    def keyword_list(self) -> list[str]:
        return [k.strip() for k in self.keywords.split(",") if k.strip()]

    @property
    def linkedin_title_exclude_list(self) -> list[str]:
        return [t.strip() for t in self.linkedin_title_exclude.split(",") if t.strip()]

    @property
    def linkedin_title_keep_list(self) -> list[str]:
        return [t.strip() for t in self.linkedin_title_keep.split(",") if t.strip()]


settings = Settings()
