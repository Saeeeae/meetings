from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health, jobs, results, uploads
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import configure_logging


configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(title="Meeting Minutes AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if not settings.api_key:
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)
    if not request.url.path.startswith("/api/"):
        return await call_next(request)

    provided = request.headers.get("x-api-key") or request.query_params.get("api_key")
    if provided != settings.api_key:
        return JSONResponse(
            status_code=401,
            content={"detail": "유효한 API 키가 필요합니다."},
        )
    return await call_next(request)


app.include_router(health.router)
app.include_router(uploads.router)
app.include_router(jobs.router)
app.include_router(results.router)
