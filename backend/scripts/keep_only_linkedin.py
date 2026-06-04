"""
Nettoie la base en supprimant toutes les offres non-LinkedIn.

Les offres LinkedIn sont conservées. Les offres wttj, smartrecruiters, greenhouse,
workday, themuse sont supprimées définitivement (pas un masquage — quand on
réactivera WTTJ plus tard, elles reviendront fraîches).

Usage :
    # Dry-run (affiche sans toucher) :
    DRY_RUN=1 TURSO_DATABASE_URL=... TURSO_AUTH_TOKEN=... .venv/bin/python backend/scripts/keep_only_linkedin.py

    # Applique :
    TURSO_DATABASE_URL=... TURSO_AUTH_TOKEN=... .venv/bin/python backend/scripts/keep_only_linkedin.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.db.database import SessionLocal, init_db
from backend.db.models import Job

DRY_RUN = os.getenv("DRY_RUN", "0") not in ("0", "false", "")

print(f"{'[DRY-RUN] ' if DRY_RUN else ''}Nettoyage — conservation uniquement des offres LinkedIn\n")

init_db()
with SessionLocal() as session:
    all_jobs = session.query(Job).all()
    to_delete = [j for j in all_jobs if j.source != "linkedin"]
    to_keep   = [j for j in all_jobs if j.source == "linkedin"]

    by_source: dict[str, int] = {}
    for j in to_delete:
        by_source[j.source] = by_source.get(j.source, 0) + 1

    print(f"Total en base   : {len(all_jobs)}")
    print(f"LinkedIn gardés : {len(to_keep)}")
    print(f"À supprimer     : {len(to_delete)}")
    for src, n in sorted(by_source.items()):
        print(f"  - {src}: {n}")

    if not DRY_RUN and to_delete:
        for job in to_delete:
            session.delete(job)
        session.commit()
        print(f"\n✓ {len(to_delete)} offres supprimées. Base nettoyée.")
    elif DRY_RUN:
        print("\n→ Relance sans DRY_RUN=1 pour appliquer.")
    else:
        print("\n✓ Rien à supprimer.")
