import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


logger = logging.getLogger(__name__)


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return database_url


class Base(DeclarativeBase):
    pass


engine = create_engine(_normalize_database_url(settings.database_url), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import job, result  # noqa: F401

    if _run_alembic_migrations():
        return

    if settings.app_env.strip().lower() == "production":
        raise RuntimeError(
            "Alembic migrations could not run. Refusing to fall back to create_all() "
            "in production because schema drift would go unnoticed."
        )
    logger.warning("Alembic not available; falling back to Base.metadata.create_all().")
    Base.metadata.create_all(bind=engine)


def _run_alembic_migrations() -> bool:
    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    if not alembic_ini.exists():
        return False
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError:
        return False

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(alembic_ini.parent / "migrations"))
    cfg.set_main_option("sqlalchemy.url", _normalize_database_url(settings.database_url))
    command.upgrade(cfg, "head")
    return True
