from pathlib import Path

from sqlalchemy import create_engine
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


def init_db() -> None:
    from . import models  # noqa: F401  (enregistre les tables sur Base)

    Base.metadata.create_all(engine)
