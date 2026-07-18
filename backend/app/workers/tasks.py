import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.job import Job
from app.models.result import Result
from app.services.alignment_service import AlignmentService
from app.services.diarization_service import get_diarization_service
from app.services.lexicon_service import LexiconCorrectionService
from app.services.llm_service import get_llm_service
from app.services.media_service import MediaService
from app.services.minutes_service import MinutesService
from app.services.stage_subprocess_service import StageSubprocessService
from app.services.stt_service import get_stt_service
from app.services.vllm_service import OnDemandVLLM
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


PROGRESS_BY_STEP = {
    "uploaded": 5,
    "preprocessing": 15,
    "stt": 35,
    "diarization": 55,
    "alignment": 65,
    "llm_startup": 70,
    "script_cleanup": 75,
    "minutes_generation": 85,
    "summary_generation": 95,
    "completed": 100,
}


_pub_client: redis.Redis | None = None


def _publish_job_event(job: Job) -> None:
    global _pub_client
    if _pub_client is None:
        try:
            _pub_client = redis.Redis.from_url(settings.redis_url)
        except Exception as exc:
            logger.warning("Failed to init Redis publisher: %s", exc)
            return
    payload = json.dumps(
        {
            "job_id": job.id,
            "status": job.status,
            "progress": job.progress,
            "current_step": job.current_step,
            "error_message": job.error_message,
        }
    )
    try:
        _pub_client.publish(f"job:{job.id}", payload)
    except redis.RedisError as exc:
        logger.warning("Failed to publish job event for %s: %s", job.id, exc)


def _set_job_step(db: Session, job: Job, step: str, status: str = "processing") -> None:
    job.status = status
    job.current_step = step
    job.progress = PROGRESS_BY_STEP.get(step, job.progress)
    db.commit()
    db.refresh(job)
    _publish_job_event(job)


def _fail_job(db: Session, job: Job, message: str) -> None:
    job.status = "failed"
    job.current_step = "failed"
    job.progress = min(job.progress or 0, 99)
    job.error_message = message
    db.commit()
    _publish_job_event(job)


def _should_run_gpu_stage_in_subprocess(provider: str) -> bool:
    return settings.gpu_stage_subprocess and provider.lower() != "mock"


def _run_stt(audio_path: str) -> dict:
    if _should_run_gpu_stage_in_subprocess(settings.stt_provider):
        logger.info("Running STT in a subprocess to release GPU memory after completion.")
        return StageSubprocessService().run_stt(audio_path)
    return get_stt_service().transcribe(audio_path)


def _run_diarization(audio_path: str) -> list[dict]:
    if _should_run_gpu_stage_in_subprocess(settings.diarization_provider):
        logger.info("Running diarization in a subprocess to release GPU memory after completion.")
        return StageSubprocessService().run_diarization(audio_path)
    return get_diarization_service().diarize(audio_path)


def _cleanup_artifacts(job: Job, processed_audio_path: str | None) -> None:
    try:
        if settings.cleanup_uploads_on_success and job.file_path:
            Path(job.file_path).unlink(missing_ok=True)
        if settings.cleanup_processed_on_success and processed_audio_path:
            Path(processed_audio_path).unlink(missing_ok=True)
    except OSError as cleanup_error:
        logger.warning("Failed to clean up artifacts for job %s: %s", job.id, cleanup_error)


def _purge_expired_artifacts(db: Session) -> None:
    retention_days = settings.retention_days
    if retention_days <= 0:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    expired = (
        db.query(Job)
        .filter(Job.updated_at < cutoff)
        .filter(Job.status.in_(["completed", "failed"]))
        .all()
    )
    if not expired:
        return

    processed_dir = settings.storage_dir / "processed"
    purged = 0
    for job in expired:
        try:
            if job.file_path:
                Path(job.file_path).unlink(missing_ok=True)
            (processed_dir / f"{job.id}.wav").unlink(missing_ok=True)
            purged += 1
        except OSError as exc:
            logger.warning("Failed to purge artifacts for job %s: %s", job.id, exc)
    if purged:
        logger.info("Purged audio artifacts for %d job(s) past %d-day retention.", purged, retention_days)


@celery_app.task(name="app.workers.tasks.process_job")
def process_job(job_id: str) -> None:
    db = SessionLocal()

    try:
        job = db.get(Job, job_id)
        if job is None:
            logger.error("Job not found: %s", job_id)
            return
        if job.status in {"processing", "completed"}:
            logger.info("Skipping duplicate job (status=%s): %s", job.status, job_id)
            return

        try:
            _purge_expired_artifacts(db)
        except Exception:
            logger.exception("Opportunistic retention purge failed; continuing.")

        _set_job_step(db, job, "preprocessing")
        audio_path = MediaService().preprocess(job.file_path, job.id)

        _set_job_step(db, job, "stt")
        stt_result = _run_stt(audio_path)
        lexicon_service = LexiconCorrectionService(settings.load_lexicon_corrections())
        if lexicon_service.enabled:
            stt_result = lexicon_service.correct_stt_result(stt_result)
            logger.info("Applied the STT correction dictionary to job %s.", job.id)

        _set_job_step(db, job, "diarization")
        speaker_segments = _run_diarization(audio_path)

        _set_job_step(db, job, "alignment")
        aligned_segments = AlignmentService().align(
            stt_result.get("segments", []),
            speaker_segments,
            words=stt_result.get("words", []),
        )
        if lexicon_service.enabled:
            aligned_segments = lexicon_service.correct_segments(aligned_segments)

        minutes_service = MinutesService()
        raw_transcript = minutes_service.build_raw_transcript(stt_result)
        speaker_transcript = minutes_service.build_speaker_transcript(aligned_segments)

        if settings.vllm_on_demand:
            _set_job_step(db, job, "llm_startup")

        detected_language = str(stt_result.get("language") or settings.stt_language or "")

        with OnDemandVLLM():
            llm_service = get_llm_service(language=detected_language)

            _set_job_step(db, job, "script_cleanup")
            cleaned_transcript = llm_service.cleanup_transcript(speaker_transcript)

            _set_job_step(db, job, "minutes_generation")
            meeting_minutes = llm_service.generate_minutes(cleaned_transcript)

            _set_job_step(db, job, "summary_generation")
            summary = llm_service.generate_summary(cleaned_transcript)

        existing_result = db.query(Result).filter(Result.job_id == job.id).one_or_none()
        if existing_result:
            existing_result.raw_transcript = raw_transcript
            existing_result.speaker_transcript = speaker_transcript
            existing_result.cleaned_transcript = cleaned_transcript
            existing_result.meeting_minutes = meeting_minutes
            existing_result.summary = summary
            existing_result.segments_json = aligned_segments
        else:
            db.add(
                Result(
                    job_id=job.id,
                    raw_transcript=raw_transcript,
                    speaker_transcript=speaker_transcript,
                    cleaned_transcript=cleaned_transcript,
                    meeting_minutes=meeting_minutes,
                    summary=summary,
                    segments_json=aligned_segments,
                )
            )

        _set_job_step(db, job, "completed", status="completed")
        logger.info("Job completed: %s", job.id)
        _cleanup_artifacts(job, audio_path)

    except Exception:
        logger.exception("Job failed: %s", job_id)
        job = db.get(Job, job_id)
        if job is not None:
            _fail_job(db, job, "분석에 실패했습니다. 업로드한 파일을 확인하거나 관리자에게 문의해주세요.")
    finally:
        db.close()
