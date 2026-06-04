import html
from datetime import UTC, datetime

import httpx

from ..config import settings
from ..db.models import Job

_JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
_MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
_MEDALS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]


class TelegramUnavailable(Exception):
    """Levée quand le bot Telegram n'est pas configuré (token/chat_id manquant)."""


API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _format(jobs: list[Job], top: int = 5) -> str:
    now = datetime.now()
    date_str = f"{_JOURS[now.weekday()]} {now.day} {_MOIS[now.month - 1]}"
    n = len(jobs)
    plural_s = "s" if n > 1 else ""

    lines = [
        f"🔔 <b>Internship Radar · {date_str}</b>",
        "",
        f"📥 <b>{n} nouvelle{plural_s} offre{plural_s}</b> trouvée{plural_s} ce matin",
    ]

    ranked = sorted(jobs, key=lambda j: (j.score_ai is None, -(j.score_ai or 0)))
    top_jobs = ranked[:top]

    if top_jobs:
        lines.append("")
        lines.append("<b>── Top du jour ──</b>")

        for i, job in enumerate(top_jobs):
            medal = _MEDALS[i] if i < len(_MEDALS) else "▪️"
            score = job.score_ai
            score_str = f"<b>{score}/100</b>" if score is not None else "—"
            title = html.escape(job.title or "Sans titre")
            company = html.escape(job.company or "")
            location = html.escape((job.location or "").split(",")[0].strip())
            url = html.escape(job.url or "", quote=True)
            source = html.escape(job.source or "")

            job_link = f'<a href="{url}">{title}</a>' if url else title
            lines.append("")
            lines.append(f"{medal} {job_link}")

            meta: list[str] = []
            if company:
                meta.append(f"🏢 {company}")
            if location:
                meta.append(f"📍 {location}")
            meta.append(f"⭐ {score_str}")
            meta.append(f"<code>{source}</code>")
            lines.append("   " + " · ".join(meta))

    if n > top:
        rest = n - top
        lines.append("")
        lines.append(
            f"<i>… et {rest} autre{'s' if rest > 1 else ''} offre{'s' if rest > 1 else ''} à découvrir</i>"
        )

    if settings.dashboard_url:
        lines.append("")
        lines.append(
            f'<a href="{html.escape(settings.dashboard_url, quote=True)}">📊 Ouvrir le dashboard →</a>'
        )

    return "\n".join(lines)


def _days_since(dt: datetime | None) -> int | None:
    """Nombre de jours écoulés depuis dt (tolère les datetimes naïfs venant de SQLite)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (datetime.now(UTC) - dt).days


def _format_follow_ups(jobs: list[Job]) -> str:
    """Message de rappel des relances à faire (candidatures postulées sans réponse)."""
    n = len(jobs)
    plural = "s" if n > 1 else ""
    lines = [f"📌 <b>{n} relance{plural} à faire</b>", ""]

    for job in jobs:
        title = html.escape(job.title or "Sans titre")
        company = html.escape(job.company or "")
        url = html.escape(job.url or "", quote=True)
        link = f'<a href="{url}">{title}</a>' if url else title
        line = f"• {link}"
        if company:
            line += f" — {company}"
        days = _days_since(job.applied_at)
        if days is not None:
            line += f" <i>(postulé il y a {days} j)</i>"
        lines.append(line)

    if settings.dashboard_url:
        lines.append("")
        lines.append(
            f'<a href="{html.escape(settings.dashboard_url, quote=True)}">📊 Ouvrir le dashboard →</a>'
        )
    return "\n".join(lines)


def _send(text: str) -> None:
    """Envoie un message Telegram. Lève TelegramUnavailable si non configuré."""
    if not settings.telegram_enabled:
        raise TelegramUnavailable("telegram_enabled=False")
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise TelegramUnavailable("telegram_bot_token ou telegram_chat_id manquant")
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    url = API_URL.format(token=settings.telegram_bot_token)
    resp = httpx.post(url, json=payload, timeout=settings.request_timeout)
    resp.raise_for_status()


def notify_new_jobs(jobs: list[Job]) -> None:
    """Notifie les nouvelles offres. Skip propre si rien à signaler."""
    if not jobs:
        return
    _send(_format(jobs))


def notify_follow_ups(jobs: list[Job]) -> None:
    """Notifie les relances à faire. Skip propre si rien à signaler."""
    if not jobs:
        return
    _send(_format_follow_ups(jobs))
