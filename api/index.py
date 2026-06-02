"""
Point d'entrée Vercel Serverless pour l'API FastAPI.
Vercel détecte l'objet ASGI `app` et le sert directement.
"""
import sys
import os

# Vercel ajoute /var/task au PYTHONPATH, mais pas forcément le dossier projet.
# On s'assure que la racine du projet est accessible pour les imports `backend.*`.
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from backend.api.main import app  # noqa: E402 — import après le path fix

# Vercel Python runtime v3+ détecte automatiquement les apps ASGI.
# `app` est l'objet FastAPI exposé comme handler.
