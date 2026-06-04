# Internship Seeker

Agrégateur d'offres de **stage / alternance / PFE** orienté *data & sport*, avec
scoring IA, suivi de candidatures et notifications Telegram. Scrape automatiquement
chaque jour, classe les offres par pertinence, et tient à jour l'avancement des
candidatures depuis un dashboard web (utilisable sur mobile en PWA).

## Fonctionnalités

- **Scraping multi-sources** — LinkedIn (actif), + WTTJ / SmartRecruiters / Greenhouse
  / Workday (codés, désactivables en 1 ligne).
- **Scoring à 2 étages** — heuristique locale gratuite (classement instantané de
  toutes les offres) + affinage Gemini des plus prometteuses (rotation de clés pour
  multiplier le quota gratuit).
- **Fiche IA** — extraction normée (contrat, durée, télétravail, missions, compétences…).
- **Filtrage intelligent** — 3 niveaux (block dur / exclude soft / keep signal positif)
  pour ne garder que les postes pertinents pour un profil ingénieur data.
- **Suivi de candidatures** — statut, date de candidature auto, relance, réponse.
- **Notifications Telegram** — nouvelles offres + rappels de relance.
- **Dashboard** — liste filtrable, graphiques, état des lieux, corbeille, PWA mobile.
- **Authentification** — mot de passe partagé protégeant l'API.

## Architecture

| Couche | Stack |
|--------|-------|
| Backend | FastAPI + SQLAlchemy, base Turso (libSQL) en prod / SQLite en local |
| Frontend | React + Vite + Tailwind + React Query (déployé sur Vercel) |
| IA | Google Gemini 2.5-flash (scoring + extraction en 1 appel) |
| Automatisation | GitHub Actions (cron 2×/jour) |

```
backend/
  api/          FastAPI (routes, auth, schemas)
  ai/           heuristic.py (étage 1), tagger.py (Gemini), quota.py, extractor.py
  scraper/      base.py (filtrage/dédup) + sources/
  db/           modèles + migrations additives
  pipeline.py   orchestration : collect → store → backfill → tag → notify
  scripts/      maintenance one-shot (nettoyage DB)
frontend/src/   composants React
tests/          pytest (filtrage, heuristique, dédup, API, auth)
```

## Développement local

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.api.main:app --reload --port 8000

# Frontend (autre terminal)
cd frontend && npm install && npm run dev
```

Sans `.env`, l'app tourne sur SQLite local (`backend/db/jobs.db`) et l'auth est
désactivée. Copier `.env.example` vers `.env` pour configurer les clés.

### Lancer le pipeline manuellement

```bash
python main.py    # scrape + score + notifie
```

## Tests & lint

```bash
pytest              # 29 tests : filtrage, heuristique, dédup, API, auth
ruff check backend tests
```

Le CI (`.github/workflows/ci.yml`) exécute lint + tests + build front à chaque push.

## Variables d'environnement

| Variable | Rôle |
|----------|------|
| `APP_PASSWORD` | Mot de passe d'accès à l'API (vide = ouvert, **à définir en prod**) |
| `GEMINI_API_KEY` | Clé Gemini principale ([aistudio](https://aistudio.google.com/app/apikey)) |
| `GEMINI_API_KEYS` | Clés supplémentaires (autres comptes), séparées par des virgules |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Notifications Telegram |
| `DASHBOARD_URL` | Lien inclus dans les messages Telegram |
| `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` | Base distante en prod (sinon SQLite local) |
| `KEYWORDS` / `LOCATION` | Mots-clés et zone de recherche |

## Déploiement

- **Frontend + API** : Vercel (front statique + API serverless via `api/index.py`).
- **Cron** : GitHub Actions (`.github/workflows/scrape.yml`), 08h et 14h UTC.
- Définir les secrets/variables (`GEMINI_*`, `TELEGRAM_*`, `TURSO_*`, `APP_PASSWORD`)
  côté Vercel **et** GitHub Actions.
