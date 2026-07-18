import asyncio
import json
import logging
from pathlib import Path

import redis.asyncio as redis_async
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.models.job import Job
from app.schemas.job import JobStatusResponse, job_to_status_response
from app.workers.tasks import process_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["jobs"])

SSE_HEARTBEAT_SECONDS = 15
SSE_MAX_DURATION_SECONDS = 60 * 60


@router.get("/jobs", response_model=list[JobStatusResponse])
def list_jobs(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[JobStatusResponse]:
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(limit).all()
    return [job_to_status_response(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_to_status_response(job)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str, db: Session = Depends(get_db)) -> Response:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status in {"queued", "processing"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="처리 중인 노트는 삭제할 수 없습니다.",
        )

    artifact_paths = {
        Path(job.file_path) if job.file_path else None,
        settings.storage_dir / "processed" / f"{job_id}.wav",
    }
    db.delete(job)
    db.commit()

    for artifact_path in artifact_paths:
        if artifact_path is None:
            continue
        try:
            artifact_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to delete artifact for job %s: %s", job_id, exc)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _job_event_payload(job: Job) -> str:
    return json.dumps(
        {
            "job_id": job.id,
            "status": job.status,
            "progress": job.progress,
            "current_step": job.current_step,
            "error_message": job.error_message,
        },
        ensure_ascii=False,
    )


async def _job_event_stream(job_id: str, request: Request):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            yield "event: error\ndata: {\"detail\":\"Job not found\"}\n\n"
            return
        yield f"data: {_job_event_payload(job)}\n\n"
        terminal = job.status in {"completed", "failed"}
    finally:
        db.close()

    if terminal:
        return

    client = redis_async.from_url(settings.redis_url)
    pubsub = client.pubsub()
    await pubsub.subscribe(f"job:{job_id}")
    deadline = asyncio.get_event_loop().time() + SSE_MAX_DURATION_SECONDS

    try:
        while True:
            if await request.is_disconnected():
                break
            if asyncio.get_event_loop().time() > deadline:
                break

            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=SSE_HEARTBEAT_SECONDS)
            if message is None:
                yield ": heartbeat\n\n"
                continue

            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            if not data:
                continue
            yield f"data: {data}\n\n"

            try:
                parsed = json.loads(data)
                if parsed.get("status") in {"completed", "failed"}:
                    break
            except json.JSONDecodeError:
                continue
    finally:
        try:
            await pubsub.unsubscribe(f"job:{job_id}")
            await pubsub.close()
        except Exception as exc:
            logger.debug("SSE pubsub cleanup error for %s: %s", job_id, exc)
        await client.aclose()


@router.get("/jobs/{job_id}/events")
async def stream_job_events(job_id: str, request: Request) -> StreamingResponse:
    return StreamingResponse(
        _job_event_stream(job_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/jobs/{job_id}/audio")
def get_job_audio(job_id: str, db: Session = Depends(get_db)) -> FileResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    processed_path = settings.storage_dir / "processed" / f"{job_id}.wav"
    upload_path = Path(job.file_path) if job.file_path else None

    if processed_path.exists():
        return FileResponse(processed_path, media_type="audio/wav", filename=f"{job_id}.wav")
    if upload_path is not None and upload_path.exists():
        return FileResponse(upload_path, filename=upload_path.name)

    raise HTTPException(status_code=status.HTTP_410_GONE, detail="오디오 파일이 보관 기간을 지나 삭제되었습니다.")


@router.post("/jobs/{job_id}/retry", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED)
def retry_job(job_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"failed 상태의 job만 재처리할 수 있습니다. (현재 상태: {job.status})",
        )
    if not job.file_path or not Path(job.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="원본 업로드 파일이 보관 기간을 지나 삭제되었습니다. 다시 업로드해주세요.",
        )

    job.status = "queued"
    job.current_step = "uploaded"
    job.progress = 5
    job.error_message = None
    db.commit()
    db.refresh(job)

    try:
        process_job.delay(job_id)
    except Exception as exc:
        job.status = "failed"
        job.current_step = "failed"
        job.error_message = "재처리 작업을 큐에 등록하지 못했습니다."
        db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=job.error_message) from exc

    return job_to_status_response(job)
