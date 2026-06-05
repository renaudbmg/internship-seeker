"""Envoi de notifications Web Push (PWA) aux appareils abonnés.

Best-effort : si VAPID n'est pas configuré, on ne fait rien. Les abonnements
expirés (404/410) sont supprimés automatiquement.
"""

from __future__ import annotations

import json

from ..config import settings
from ..db.database import SessionLocal
from ..db.models import PushSubscription


def _private_key() -> str | None:
    key = settings.vapid_private_key
    if not key:
        return None
    # Les sauts de ligne PEM sont souvent échappés \n dans les variables d'env.
    return key.replace("\\n", "\n")


def push_enabled() -> bool:
    return bool(settings.vapid_public_key and _private_key())


def send_push(title: str, body: str, url: str | None = None) -> int:
    """Envoie une notif à tous les abonnés. Renvoie le nombre d'envois réussis."""
    if not push_enabled():
        return 0
    from pywebpush import WebPushException, webpush

    payload = json.dumps({"title": title, "body": body, "url": url or settings.dashboard_url or "/"})
    claims = {"sub": settings.vapid_subject}
    sent = 0
    with SessionLocal() as session:
        subs = session.query(PushSubscription).all()
        for sub in subs:
            info = {
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            }
            try:
                webpush(
                    subscription_info=info,
                    data=payload,
                    vapid_private_key=_private_key(),
                    vapid_claims=dict(claims),
                )
                sent += 1
            except WebPushException as exc:
                status = getattr(exc.response, "status_code", None)
                if status in (404, 410):  # abonnement expiré → on le retire
                    session.delete(sub)
            except Exception:
                pass
        session.commit()
    return sent
