from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..config import settings


class Base(DeclarativeBase):
    pass


def _clean(value: str) -> str:
    # pydantic-settings ne retire pas toujours les guillemets d'un .env
    return value.strip().strip('"').strip("'")


def _make_engine():
    """Turso (libSQL) si configuré, sinon fichier SQLite local."""
    if settings.turso_database_url:
        host = (
            _clean(settings.turso_database_url)
            .replace("libsql://", "")
            .replace("https://", "")
            .rstrip("/")
        )
        url = f"sqlite+libsql://{host}/?secure=true"
        connect_args = {}
        if settings.turso_auth_token:
            # libsql_experimental veut le JWT en kwarg, pas dans l'URL
            connect_args["auth_token"] = _clean(settings.turso_auth_token)
        return create_engine(url, future=True, connect_args=connect_args)

    db_file = Path(settings.db_path).resolve()
    db_file.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_file}", future=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


# Colonnes ajoutées après coup : create_all ne modifie jamais une table existante,
# donc on applique des ALTER additifs idempotents au démarrage (prod + cron se migrent seuls).
_ADDITIVE_COLUMNS: dict[str, str] = {
    "details_ai": "TEXT",
    "logo_url": "TEXT",
}


def _migrate(engine) -> None:
    inspector = inspect(engine)
    if "jobs" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("jobs")}
    with engine.begin() as conn:
        for name, sql_type in _ADDITIVE_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {name} {sql_type}"))


def init_db() -> None:
    from . import models  # noqa: F401  (enregistre les tables sur Base)

    Base.metadata.create_all(engine)
    _migrate(engine)
