from __future__ import annotations

import time
from typing import Callable

# Free tier gemini-2.5-flash : ~10 req/min (RPM) et ~250 req/jour (RPD).
# Le goulot est le RPM. On rythme donc les appels sous cette limite, et sur une
# 429 (qui peut être « par minute », transitoire) on patiente puis on réessaie ;
# on ne conclut à l'épuisement JOURNALIER qu'après plusieurs back-offs consécutifs
# infructueux (une limite par minute, elle, se serait libérée entre-temps).
PACE_SECONDS = 6.5  # entre 2 appels réussis → ~9 req/min, sous la limite RPM
BACKOFF_SECONDS = 65.0  # > 1 min : laisse la fenêtre par minute se réinitialiser
MAX_CONSECUTIVE_QUOTA = 3  # 3 back-offs ratés d'affilée ⇒ quota journalier épuisé


def is_quota_error(exc: Exception) -> bool:
    """Vrai si l'exception traduit un dépassement de quota / rate-limit Gemini (429)."""
    name = type(exc).__name__
    text = str(exc).lower()
    return (
        name in ("ResourceExhausted", "TooManyRequests")
        or "resource_exhausted" in text
        or "quota" in text
        or "rate limit" in text
        or "429" in text
    )


def run_quota_loop(
    jobs: list,
    process_one: Callable[[object], None],
    *,
    label: str,
) -> tuple[int, bool]:
    """Traite `jobs` un par un via `process_one`, en maximisant le quota Gemini.

    - rythme : pause `PACE_SECONDS` après chaque appel réussi (reste sous le RPM) ;
    - sur 429 : back-off `BACKOFF_SECONDS` puis on RÉESSAIE la même offre. Si
      `MAX_CONSECUTIVE_QUOTA` 429 consécutives malgré les back-offs → quota
      journalier épuisé, on s'arrête et on laisse le reste en file ;
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
            if is_quota_error(exc):
                consecutive_quota += 1
                if consecutive_quota >= MAX_CONSECUTIVE_QUOTA:
                    print(f"[{label}] quota JOURNALIER Gemini atteint après {done} offres — reste en file")
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
