from __future__ import annotations


def is_quota_error(exc: Exception) -> bool:
    """Vrai si l'exception traduit un dépassement de quota / rate-limit Gemini.

    Sur le free tier, une fois le quota journalier épuisé, chaque appel renvoie
    une ResourceExhausted (HTTP 429). Inutile d'insister : on stoppe la boucle et
    on laisse les offres restantes en file pour le prochain passage du cron.
    """
    name = type(exc).__name__
    text = str(exc).lower()
    return (
        name in ("ResourceExhausted", "TooManyRequests")
        or "resource_exhausted" in text
        or "quota" in text
        or "rate limit" in text
        or "429" in text
    )
