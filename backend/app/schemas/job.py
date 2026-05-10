from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UploadResponse(BaseModel):
    job_id: str
    status: str
    filename: str


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: str
    progress: int
    current_step: str
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None


def job_to_status_response(job) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_message=job.error_message,
    )
