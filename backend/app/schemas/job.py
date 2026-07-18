from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class UploadResponse(BaseModel):
    job_id: str
    status: str
    filename: str


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    filename: str
    title: str
    status: str
    progress: int
    current_step: str
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None


def job_to_status_response(job) -> JobStatusResponse:
    title = (job.title or "").strip() or Path(job.original_filename).stem or "제목 없는 노트"
    return JobStatusResponse(
        job_id=job.id,
        filename=job.original_filename,
        title=title,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_message=job.error_message,
    )
