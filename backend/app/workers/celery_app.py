import logging

from celery import Celery
from celery.signals import worker_ready, worker_shutdown

from app.core.config import settings


logger = logging.getLogger(__name__)

settings.validate_runtime_configuration()


celery_app = Celery(
    "meeting_minutes_ai",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # acks_late + Redis: an unacked task is redelivered after visibility_timeout,
    # so it must exceed the longest possible job or duplicates get queued mid-run.
    broker_transport_options={
        "visibility_timeout": settings.job_time_limit_seconds + 3600,
    },
    task_time_limit=settings.job_time_limit_seconds,
    task_soft_time_limit=max(60, settings.job_time_limit_seconds - 300),
    beat_schedule={
        "purge-expired-artifacts": {
            "task": "app.workers.tasks.purge_expired_artifacts",
            "schedule": 6 * 3600.0,
        },
    },
)


@worker_ready.connect
def _on_worker_ready(**_: object) -> None:
    from app.core.database import SessionLocal, init_db
    from app.models.job import Job
    from app.workers.tasks import process_job

    init_db()

    db = SessionLocal()
    try:
        if not settings.recover_interrupted_jobs:
            return

        recoverable = db.query(Job).filter(Job.status.in_(["queued", "processing"])).all()
        if not recoverable:
            return
        logger.warning("Requeueing %d interrupted or queued job(s).", len(recoverable))
        job_ids: list[str] = []
        for job in recoverable:
            job.status = "queued"
            job.current_step = "uploaded"
            job.progress = 5
            job.error_message = None
            job_ids.append(job.id)
        db.commit()
    finally:
        db.close()

    for job_id in job_ids:
        process_job.delay(job_id)


@worker_shutdown.connect
def _on_worker_shutdown(**_: object) -> None:
    from app.services.vllm_service import shutdown_warm_vllm

    shutdown_warm_vllm()
