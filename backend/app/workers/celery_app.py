import logging

from celery import Celery
from celery.signals import worker_ready, worker_shutdown

from app.core.config import settings


logger = logging.getLogger(__name__)


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
)


@worker_ready.connect
def _on_worker_ready(**_: object) -> None:
    from app.core.database import SessionLocal, init_db
    from app.models.job import Job

    init_db()

    db = SessionLocal()
    try:
        stale = db.query(Job).filter(Job.status == "processing").all()
        if not stale:
            return
        logger.warning("Recovering %d orphan job(s) left in 'processing' state.", len(stale))
        for job in stale:
            job.status = "failed"
            job.current_step = "failed"
            job.progress = min(job.progress or 0, 99)
            job.error_message = "워커가 재시작되어 분석이 중단되었습니다. 다시 업로드해주세요."
        db.commit()
    finally:
        db.close()


@worker_shutdown.connect
def _on_worker_shutdown(**_: object) -> None:
    from app.services.vllm_service import shutdown_warm_vllm

    shutdown_warm_vllm()
