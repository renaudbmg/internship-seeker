"""
Nettoyage de la base : masque les offres dont le titre est hors-cible ingénieur data.

Usage :
    TURSO_DATABASE_URL=libsql://... TURSO_AUTH_TOKEN=... python backend/scripts/cleanup_noise.py

    # Dry-run (affiche sans toucher à la DB) :
    DRY_RUN=1 TURSO_DATABASE_URL=... python backend/scripts/cleanup_noise.py

Ce script masque (hidden=True) les offres actives dont le titre matche la blocklist
ou la liste d'exclusion sans signal positif — il ne supprime rien, tout reste
récupérable via la Corbeille du dashboard.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.config import settings
from backend.db.database import SessionLocal, init_db
from backend.db.models import Job
from backend.scraper.base import should_exclude_title

DRY_RUN = os.getenv("DRY_RUN", "0") not in ("0", "false", "")

exclude = settings.title_exclude_list
keep = settings.title_keep_list
block = settings.title_block_list

print(f"{'[DRY-RUN] ' if DRY_RUN else ''}Nettoyage des offres hors-cible...")
print(f"  block  : {len(block)} termes")
print(f"  exclude: {len(exclude)} termes  (soft, overridé par keep)")
print(f"  keep   : {len(keep)} termes")
print()

init_db()
masked = []
with SessionLocal() as session:
    active_jobs = (
        session.query(Job)
        .filter(Job.hidden.isnot(True))
        .all()
    )
    print(f"{len(active_jobs)} offres actives en base\n")

    for job in active_jobs:
        if should_exclude_title(job.title, exclude, keep, block):
            masked.append(job)
            if not DRY_RUN:
                job.hidden = True

    if not DRY_RUN:
        session.commit()

print(f"{'Masquerait' if DRY_RUN else 'Masqué'} {len(masked)} offres :\n")
for job in masked:
    print(f"  [{job.source}] {job.title} — {job.company}")

print(f"\n{'→ Relance sans DRY_RUN=1 pour appliquer.' if DRY_RUN else '✓ Terminé. Offres visibles dans la Corbeille du dashboard.'}")
