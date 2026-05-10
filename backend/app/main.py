from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, jobs, results, uploads
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import configure_logging


configure_logging()

app = FastAPI(title="Meeting Minutes AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    init_db()


app.include_router(health.router)
app.include_router(uploads.router)
app.include_router(jobs.router)
app.include_router(results.router)
