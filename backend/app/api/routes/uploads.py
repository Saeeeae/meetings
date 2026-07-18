import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import Job
from app.schemas.job import UploadResponse
from app.services.media_service import MediaService
from app.services.storage_service import StorageService
from app.utils.file_utils import validate_upload_file
from app.workers.tasks import process_job

router = APIRouter(prefix="/api", tags=["uploads"])


@router.post("/uploads", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)) -> UploadResponse:
    validate_upload_file(file)

    job_id = str(uuid.uuid4())
    stored_file = await StorageService().save_upload_file(file, job_id)

    # Extension/MIME headers are client-controlled; probe the stored bytes for
    # an actual audio stream before queueing GPU work on them.
    if not MediaService().has_audio_stream(stored_file.file_path):
        Path(stored_file.file_path).unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="업로드한 파일에서 오디오 스트림을 찾을 수 없습니다. 녹음 파일인지 확인해주세요.",
        )

    job = Job(
        id=job_id,
        original_filename=stored_file.original_filename,
        title=Path(stored_file.original_filename).stem or "제목 없는 노트",
        stored_filename=stored_file.stored_filename,
        file_path=stored_file.file_path,
        status="queued",
        progress=5,
        current_step="uploaded",
        recording_source="upload",
    )
    db.add(job)
    db.commit()

    try:
        process_job.delay(job_id)
    except Exception as exc:
        job.status = "failed"
        job.current_step = "failed"
        job.error_message = "분석 작업을 큐에 등록하지 못했습니다."
        db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=job.error_message) from exc

    return UploadResponse(job_id=job.id, status=job.status, filename=job.original_filename)
