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
    linkedin_experience_level: str | None = None  # ex "1"=stage, "2"=débutant (filtre f_E)

    # Source: The Muse (gratuite, sans clé) — socle de secours, désactivé par défaut
    themuse_enabled: bool = False
    themuse_api_key: str | None = None

    # Source: ATS SmartRecruiters (API publique, sans clé). Marques sport (ex. Salomon).
    # `smartrecruiters_companies` = identifiants séparés par des virgules.
    smartrecruiters_enabled: bool = True
    smartrecruiters_companies: str = "Salomon"

    # Source: ATS Greenhouse (API publique « job board », sans clé). Ex. On Running.
    # `greenhouse_boards` = identifiants de board séparés par des virgules.
    greenhouse_enabled: bool = True
    greenhouse_boards: str = "onrunning"

    # Scoring IA (Sprint 2) — Gemini Flash
    scoring_enabled: bool = True
    gemini_api_key: str | None = None  # https://aistudio.google.com/app/apikey
    gemini_model: str = "gemini-2.0-flash"

    # Source: France Travail / API Offres d'emploi v2 (officielle, gratuite, credentials requis)
    # Inscription: https://francetravail.io  -> créer une application -> API "Offres d'emploi v2"
    france_travail_enabled: bool = False
    france_travail_client_id: str | None = None
    france_travail_client_secret: str | None = None

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


settings = Settings()
