import html

import httpx

from ..config import settings
from ..db.models import Job


class TelegramUnavailable(Exception):
    """Levée quand le bot Telegram n'est pas configuré (token/chat_id manquant)."""


API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _format(jobs: list[Job], top: int = 5) -> str:
    """Construit le message HTML : compteur + top offres par score + lien dashboard."""
    n = len(jobs)
    lines = [f"🎯 <b>{n} nouvelle{'s' if n > 1 else ''} offre{'s' if n > 1 else ''}</b> ce matin"]

    ranked = sorted(jobs, key=lambda j: (j.score_ai is None, -(j.score_ai or 0)))
    for job in ranked[:top]:
        score = f"{job.score_ai}" if job.score_ai is not None else "—"
        title = html.escape(job.title or "")
        company = html.escape(job.company or "")
        url = html.escape(job.url or "", quote=True)
        label = f"<b>{score}</b> · {title}"
        if company:
            label += f" — {company}"
        lines.append(f"• <a href=\"{url}\">{label}</a>" if url else f"• {label}")

    if n > top:
        lines.append(f"… et {n - top} autre{'s' if n - top > 1 else ''}.")

    if settings.dashboard_url:
        lines.append(f"\n👉 <a href=\"{html.escape(settings.dashboard_url, quote=True)}\">Ouvrir le dashboard</a>")

    return "\n".join(lines)


def notify_new_jobs(jobs: list[Job]) -> None:
    """Envoie une notification Telegram. Skip propre si non configuré ou si rien à signaler."""
    if not jobs:
        return
    if not settings.telegram_enabled:
        raise TelegramUnavailable("telegram_enabled=False")
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise TelegramUnavailable("telegram_bot_token ou telegram_chat_id manquant")

    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": _format(jobs),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    url = API_URL.format(token=settings.telegram_bot_token)
    resp = httpx.post(url, json=payload, timeout=settings.request_timeout)
    resp.raise_for_status()
