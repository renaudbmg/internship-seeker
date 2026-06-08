"""Script one-shot : restaure TOUTES les offres masquées par l'auto-archivage.
Lancer avec : python -m backend.scripts.restore_archived [--dry-run]
"""

import sys

from backend.db.database import SessionLocal, init_db
from backend.db.models import Job

DRY_RUN = "--dry-run" in sys.argv or "DRY_RUN" in __import__("os").environ

init_db()
with SessionLocal() as session:
    hidden = session.query(Job).filter(Job.hidden.is_(True)).all()
    print(f"{len(hidden)} offres masquées trouvées")
    if DRY_RUN:
        print("DRY_RUN — aucune modification")
    else:
        for job in hidden:
            job.hidden = False
        session.commit()
        print(f"✅ {len(hidden)} offres restaurées")
