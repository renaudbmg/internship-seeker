"""Tests des étapes pipeline (hors appels réseau/Gemini)."""

from datetime import UTC, datetime, timedelta

from backend.config import settings
from backend.db.models import Job
from backend.pipeline import _auto_archive


def _add(session, **kw):
    defaults = dict(
        id="j", title="Stage Data", company="X", source="linkedin", url="u",
        status="to_review", scraped_at=datetime.now(UTC),
    )
    defaults.update(kw)
    session.add(Job(**defaults))
    session.commit()


def test_auto_archive_masque_les_anciennes_non_traitees(db_session, monkeypatch):
    monkeypatch.setattr(settings, "auto_archive_days", 45)
    old = datetime.now(UTC) - timedelta(days=60)
    _add(db_session, id="vieille", scraped_at=old)              # → archivée
    _add(db_session, id="recente")                              # récente → gardée
    _add(db_session, id="vieille_traitee", scraped_at=old, status="interested")  # traitée → gardée

    _auto_archive()

    assert db_session.get(Job, "vieille").hidden is True
    assert db_session.get(Job, "recente").hidden is not True
    assert db_session.get(Job, "vieille_traitee").hidden is not True


def test_auto_archive_desactive_si_zero(db_session, monkeypatch):
    monkeypatch.setattr(settings, "auto_archive_days", 0)
    old = datetime.now(UTC) - timedelta(days=100)
    _add(db_session, id="vieille", scraped_at=old)
    _auto_archive()
    assert db_session.get(Job, "vieille").hidden is not True
