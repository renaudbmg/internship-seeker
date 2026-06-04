"""Configuration pytest : base SQLite temporaire isolée (jamais la prod Turso)."""

import os
import tempfile

# IMPORTANT : définir l'environnement AVANT tout import de `backend.*`, car
# `settings` et l'engine SQLAlchemy sont créés au moment de l'import.
_TEST_DB = os.path.join(tempfile.gettempdir(), "internship_seeker_test.db")
os.environ["DB_PATH"] = _TEST_DB
os.environ.pop("TURSO_DATABASE_URL", None)  # ne jamais taper la prod pendant les tests
os.environ.pop("TURSO_AUTH_TOKEN", None)

import pytest  # noqa: E402

from backend.db.database import Base, SessionLocal, engine, init_db  # noqa: E402


@pytest.fixture
def db_session():
    """Base fraîche pour chaque test (drop + recreate)."""
    Base.metadata.drop_all(bind=engine)
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """TestClient FastAPI sur la base fraîche."""
    from fastapi.testclient import TestClient

    from backend.api.main import app

    return TestClient(app)
