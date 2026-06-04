from __future__ import annotations

import time
from collections.abc import Callable

# Gemini free tier (depuis la coupe Google du 7 déc. 2025) :
#   gemini-2.5-flash       → 10 RPM, 250 RPD
#   gemini-2.5-flash-lite  → 15 RPM, 1 000 RPD   ← modèle retenu (4× le quota/jour)
# Deux types de 429 très différents :
#   - RPM (par minute) : transitoire — on attend ~1 min et on réessaie la même offre ;
#   - RPD (par jour)   : épuisé pour la journée — inutile d'insister, on stoppe.
# Confondre les deux (ancien comportement) faisait stopper le pipeline au premier
# pic de RPM, ne taguant qu'une poignée d'offres alors que le quota du jour restait.
PACE_SECONDS = 13.0  # entre 2 appels réussis → ~4,6 req/min, sous la limite 5 RPM
# (gemini-2.5-flash free tier = 5 RPM → 60/5 = 12s minimum, on prend 13s de marge)
BACKOFF_SECONDS = 65.0  # > 1 min : laisse la fenêtre par minute se réinitialiser
MAX_CONSECUTIVE_QUOTA = 3  # 3 back-offs ratés d'affilée ⇒ quota journalier épuisé


def is_rate_limit_error(exc: Exception) -> bool:
    """Vrai pour tout 429 / ResourceExhausted Gemini (RPM ou RPD confondus)."""
    name = type(exc).__name__
    text = str(exc).lower()
    return (
        name in ("ResourceExhausted", "TooManyRequests")
        or "resource_exhausted" in text
        or "quota" in text
        or "rate limit" in text
        or "429" in text
    )


def is_daily_quota_error(exc: Exception) -> bool:
    """Vrai uniquement si le 429 traduit le quota JOURNALIER (RPD) épuisé.

    Le message Gemini nomme la métrique violée, ex :
      'GenerateRequestsPerDayPerProjectPerModel'    (RPD → on stoppe)
      'GenerateRequestsPerMinutePerProjectPerModel' (RPM → on réessaie)
    Si on ne peut pas trancher, on suppose RPM (transitoire) pour ne pas s'arrêter
    prématurément ; le compteur de back-offs consécutifs sert alors de garde-fou.
    """
    if not is_rate_limit_error(exc):
        return False
    text = str(exc).lower()
    daily_markers = ("perday", "per day", "per-day", "requests_per_day", "free_tier_requests")
    minute_markers = ("perminute", "per minute", "per-minute", "requests_per_minute")
    if any(m in text for m in daily_markers):
        return True
    if any(m in text for m in minute_markers):
        return False
    return False  # par défaut : on suppose RPM (transitoire) et on réessaie


def run_quota_loop(
    jobs: list,
    process_one: Callable[[object], None],
    *,
    label: str,
) -> tuple[int, bool]:
    """Traite `jobs` un par un via `process_one`, en maximisant le quota Gemini.

    - rythme : pause `PACE_SECONDS` après chaque appel réussi (reste sous le RPM) ;
    - sur 429 explicitement JOURNALIER (RPD) : on stoppe tout de suite ;
    - sur 429 par minute (RPM) : back-off `BACKOFF_SECONDS` puis on RÉESSAIE la même
      offre. Après `MAX_CONSECUTIVE_QUOTA` back-offs infructueux d'affilée, on suppose
      le quota journalier épuisé et on s'arrête (reste en file pour le prochain run) ;
    - autre erreur : on saute l'offre (ne bloque pas les suivantes).

    `process_one` doit faire le travail ET committer (commit par offre = reprise sûre).
    Renvoie (nombre traité, arrêté_pour_quota_journalier).
    """
    done = 0
    consecutive_quota = 0
    i = 0
    while i < len(jobs):
        job = jobs[i]
        try:
            process_one(job)
        except Exception as exc:
            if is_rate_limit_error(exc):
                if is_daily_quota_error(exc):
                    print(f"[{label}] quota JOURNALIER Gemini épuisé après {done} offres — reste en file")
                    return done, True
                consecutive_quota += 1
                if consecutive_quota >= MAX_CONSECUTIVE_QUOTA:
                    print(
                        f"[{label}] {MAX_CONSECUTIVE_QUOTA} rate-limits consécutifs malgré les "
                        f"back-offs — on suppose le quota journalier épuisé après {done} offres"
                    )
                    return done, True
                print(
                    f"[{label}] rate-limit par minute (tentative {consecutive_quota}/"
                    f"{MAX_CONSECUTIVE_QUOTA}) — pause {BACKOFF_SECONDS:.0f}s puis reprise…"
                )
                time.sleep(BACKOFF_SECONDS)
                continue  # on réessaie la MÊME offre (i inchangé)
            title = getattr(job, "title", "?")
            print(f"[{label}] échec « {str(title)[:40]} »: {exc!r}")
            i += 1
            time.sleep(5)
            continue
        consecutive_quota = 0
        done += 1
        i += 1
        time.sleep(PACE_SECONDS)
    return done, False
