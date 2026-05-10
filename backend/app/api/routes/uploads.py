import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import Job
from app.schemas.job import UploadResponse
from app.services.storage_service import StorageService
from app.utils.file_utils import validate_upload_file
from app.workers.tasks import process_job

router = APIRouter(prefix="/api", tags=["uploads"])


@router.post("/uploads", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)) -> UploadResponse:
    validate_upload_file(file)

    job_id = str(uuid.uuid4())
    stored_file = await StorageService().save_upload_file(file, job_id)

    job = Job(
        id=job_id,
        original_filename=stored_file.original_filename,
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
        job.error_message = "Failed to enqueue analysis job."
        db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=job.error_message) from exc

    return UploadResponse(job_id=job.id, status=job.status, filename=job.original_filename)
