from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..db.database import init_db
from .auth import require_auth
from .routes import jobs, push, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Internship Seeker API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # localhost (dev, n'importe quel port) + tout déploiement *.vercel.app (front prod)
    allow_origin_regex=r"(http://(localhost|127\.0\.0\.1):\d+|https://.*\.vercel\.app)",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/auth/check")
def auth_check(_: None = Depends(require_auth)) -> dict:
    """Valide le mot de passe (utilisé par l'écran de login du frontend)."""
    return {"ok": True}


# stats avant jobs : /jobs/stats doit matcher avant /jobs/{job_id}
# require_auth protège toutes les routes /jobs (lecture ET écriture).
app.include_router(stats.router, dependencies=[Depends(require_auth)])
app.include_router(jobs.router, dependencies=[Depends(require_auth)])
# push : /push/vapid-public-key public, /push/subscribe protégé (auth dans le routeur)
app.include_router(push.router)
