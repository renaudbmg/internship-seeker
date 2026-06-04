"""
Authentification simple par mot de passe partagé (app mono-utilisateur).

Le frontend envoie le mot de passe en header (`Authorization: Bearer <pwd>` ou
`X-API-Key: <pwd>`). Le backend le compare à APP_PASSWORD en temps constant.

Si APP_PASSWORD n'est pas défini, l'auth est DÉSACTIVÉE — pratique en dev local.
⚠️ En prod (Vercel), définir APP_PASSWORD pour protéger les données perso.
"""

import secrets

from fastapi import Header, HTTPException

from ..config import settings


def require_auth(
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None),
) -> None:
    expected = settings.app_password
    if not expected:
        return  # auth désactivée (aucun mot de passe configuré)

    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()

    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Non autorisé")
