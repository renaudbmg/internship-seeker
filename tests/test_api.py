"""Tests API : authentification, listing/filtrage, suivi, masquage."""

import pytest

from backend.config import settings
from backend.db.models import Job


def _seed(session, **kw):
    defaults = dict(
        id="j1", title="Stage Data Analyst", company="Salomon", source="linkedin",
        url="https://x", location="Annecy", description="SQL Python", score_heuristic=80,
    )
    defaults.update(kw)
    job = Job(**defaults)
    session.add(job)
    session.commit()
    return job


# ---------- Authentification ----------

@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, "app_password", "secret")
    yield "secret"


def test_health_public(client):
    assert client.get("/health").status_code == 200


def test_jobs_refuse_sans_token(client, auth_on):
    assert client.get("/jobs").status_code == 401


def test_jobs_refuse_mauvais_token(client, auth_on):
    r = client.get("/jobs", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_jobs_ok_bon_token(client, auth_on, db_session):
    _seed(db_session)
    r = client.get("/jobs", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_auth_desactivee_sans_password(client, db_session):
    # settings.app_password vaut None par défaut → accès libre
    _seed(db_session)
    assert client.get("/jobs").status_code == 200


# ---------- Listing / filtrage ----------

def test_liste_exclut_masquees(client, db_session):
    _seed(db_session, id="visible")
    _seed(db_session, id="cachee", hidden=True)
    items = client.get("/jobs").json()
    assert items["total"] == 1
    assert items["items"][0]["id"] == "visible"


def test_corbeille_montre_masquees(client, db_session):
    _seed(db_session, id="cachee", hidden=True)
    r = client.get("/jobs?hidden=true").json()
    assert r["total"] == 1


def test_filtre_score_min_sur_score_effectif(client, db_session):
    _seed(db_session, id="haut", score_heuristic=90)
    _seed(db_session, id="bas", score_heuristic=20)
    r = client.get("/jobs?score_min=50").json()
    assert {j["id"] for j in r["items"]} == {"haut"}


# ---------- Suivi de candidature ----------

def test_passage_applied_date_automatiquement(client, db_session):
    _seed(db_session)
    r = client.patch("/jobs/j1/status", json={"status": "applied"})
    body = r.json()
    assert body["status"] == "applied"
    assert body["applied_at"] is not None
    assert body["response"] == "pending"


def test_tracking_met_a_jour_relance_et_reponse(client, db_session):
    _seed(db_session)
    r = client.patch("/jobs/j1/tracking", json={"follow_up_at": "2026-01-01", "response": "positive"})
    body = r.json()
    assert body["response"] == "positive"
    assert body["follow_up_at"].startswith("2026-01-01")


def test_tracking_refuse_reponse_invalide(client, db_session):
    _seed(db_session)
    r = client.patch("/jobs/j1/tracking", json={"response": "banane"})
    assert r.status_code == 422


def test_repasser_a_traiter_efface_le_suivi(client, db_session):
    # postulé + relance programmée
    _seed(db_session)
    client.patch("/jobs/j1/status", json={"status": "applied"})
    client.patch("/jobs/j1/tracking", json={"follow_up_at": "2026-01-01", "response": "pending"})
    # correction d'erreur : retour à « à traiter » → le suivi doit être effacé
    body = client.patch("/jobs/j1/status", json={"status": "to_review"}).json()
    assert body["applied_at"] is None
    assert body["follow_up_at"] is None
    assert body["response"] is None


def test_rejected_supprime_la_relance(client, db_session):
    _seed(db_session)
    client.patch("/jobs/j1/status", json={"status": "applied"})
    client.patch("/jobs/j1/tracking", json={"follow_up_at": "2026-01-01", "response": "pending"})
    body = client.patch("/jobs/j1/status", json={"status": "rejected"}).json()
    assert body["follow_up_at"] is None  # plus de rappel fantôme


# ---------- Payload allégé liste vs détail ----------

def test_liste_sans_description(client, db_session):
    _seed(db_session, description="Longue description confidentielle")
    item = client.get("/jobs").json()["items"][0]
    assert "description" not in item  # liste allégée


def test_detail_avec_description_et_marque_vu(client, db_session):
    _seed(db_session, description="Missions data SQL", seen=False)
    detail = client.get("/jobs/j1").json()
    assert detail["description"] == "Missions data SQL"
    # l'ouverture du détail marque l'offre comme vue
    assert client.get("/jobs/j1").json()["seen"] is True


# ---------- Seuil heuristique (économie quota) ----------

def test_progress_exclut_sous_seuil(client, db_session):
    _seed(db_session, id="bonne", score_heuristic=90, score_ai=None)
    _seed(db_session, id="faible", score_heuristic=10, score_ai=None)  # sous le seuil 25
    prog = client.get("/jobs/progress").json()
    # seule l'offre au-dessus du seuil compte comme « à tagger »
    assert prog["pending_scoring"] == 1


# ---------- Nouveautés (non vues) ----------

def test_filtre_unseen(client, db_session):
    _seed(db_session, id="vue", seen=True)
    _seed(db_session, id="neuve", seen=False)
    r = client.get("/jobs?unseen=true").json()
    assert {j["id"] for j in r["items"]} == {"neuve"}


# ---------- Export CSV ----------

def test_export_csv_candidatures(client, db_session):
    _seed(db_session, id="postule", status="applied")
    _seed(db_session, id="autre", status="to_review")
    r = client.get("/jobs/export.csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lignes = r.text.strip().splitlines()
    assert lignes[0].startswith("Titre,Entreprise")
    # seule l'offre postulée figure (1 entête + 1 ligne)
    assert len(lignes) == 2
    assert "Salomon" in lignes[1]


# ---------- Push PWA ----------

def test_push_subscribe_et_vapid(client, db_session):
    assert client.get("/push/vapid-public-key").status_code == 200
    sub = {"endpoint": "https://fcm.test/x", "keys": {"p256dh": "a", "auth": "b"}}
    assert client.post("/push/subscribe", json=sub).json() == {"ok": True}
    # ré-abonnement même endpoint = upsert (pas de doublon)
    client.post("/push/subscribe", json=sub)
    from backend.db.models import PushSubscription
    assert db_session.query(PushSubscription).count() == 1


def test_push_subscribe_invalide(client, db_session):
    assert client.post("/push/subscribe", json={"endpoint": "", "keys": {}}).status_code == 422


def test_send_push_noop_si_non_configure(db_session, monkeypatch):
    from backend.config import settings
    from backend.notifications.push import send_push
    monkeypatch.setattr(settings, "vapid_private_key", None)
    assert send_push("t", "b") == 0  # pas de crash, 0 envoi


# ---------- Masquage ----------

def test_masquer_puis_restaurer(client, db_session):
    _seed(db_session)
    assert client.patch("/jobs/j1/hidden", json={"hidden": True}).json()["hidden"] is True
    assert client.get("/jobs").json()["total"] == 0
    assert client.patch("/jobs/j1/hidden", json={"hidden": False}).json()["hidden"] is False
    assert client.get("/jobs").json()["total"] == 1
