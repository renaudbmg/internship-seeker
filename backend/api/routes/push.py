from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...config import settings
from ...db.models import PushSubscription
from ..auth import require_auth
from ..deps import get_session
from ..schemas import PushSubscriptionIn

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key")
def vapid_public_key():
    """Clé publique VAPID, lue par le front pour s'abonner. Publique par nature."""
    return {"key": settings.vapid_public_key or ""}


@router.post("/subscribe", dependencies=[Depends(require_auth)])
def subscribe(payload: PushSubscriptionIn, session: Session = Depends(get_session)):
    """Enregistre (ou met à jour) un abonnement Web Push pour cet appareil."""
    keys = payload.keys or {}
    if not payload.endpoint or "p256dh" not in keys or "auth" not in keys:
        raise HTTPException(status_code=422, detail="Abonnement invalide")
    sub = session.get(PushSubscription, payload.endpoint)
    if sub is None:
        sub = PushSubscription(endpoint=payload.endpoint, p256dh=keys["p256dh"], auth=keys["auth"])
        session.add(sub)
    else:
        sub.p256dh, sub.auth = keys["p256dh"], keys["auth"]
    session.commit()
    return {"ok": True}
