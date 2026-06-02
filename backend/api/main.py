from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..db.database import init_db
from .routes import jobs, stats

app = FastAPI(title="Internship Seeker API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    # localhost (dev, n'importe quel port) + tout déploiement *.vercel.app (front prod)
    allow_origin_regex=r"(http://(localhost|127\.0\.0\.1):\d+|https://.*\.vercel\.app)",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# stats avant jobs : /jobs/stats doit matcher avant /jobs/{job_id}
app.include_router(stats.router)
app.include_router(jobs.router)
