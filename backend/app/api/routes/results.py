import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import Job
from app.models.result import Result
from app.schemas.result import DownloadType, ResultResponse

router = APIRouter(prefix="/api", tags=["results"])


def _get_completed_job_and_result(db: Session, job_id: str) -> tuple[Job, Result]:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"status": job.status, "progress": job.progress, "current_step": job.current_step},
        )

    result = db.query(Result).filter(Result.job_id == job_id).one_or_none()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")
    return job, result


def _result_response(job: Job, result: Result) -> ResultResponse:
    return ResultResponse(
        job_id=job.id,
        status=job.status,
        raw_transcript=result.raw_transcript,
        speaker_transcript=result.speaker_transcript,
        cleaned_transcript=result.cleaned_transcript,
        meeting_minutes=result.meeting_minutes,
        summary=result.summary,
        segments=result.segments_json,
    )


@router.get("/results/{job_id}", response_model=ResultResponse)
def get_result(job_id: str, db: Session = Depends(get_db)) -> ResultResponse:
    job, result = _get_completed_job_and_result(db, job_id)
    return _result_response(job, result)


@router.get("/results/{job_id}/download")
def download_result(
    job_id: str,
    type: DownloadType = Query(..., description="minutes, summary, transcript, cleaned_transcript, json"),
    db: Session = Depends(get_db),
) -> Response:
    job, result = _get_completed_job_and_result(db, job_id)

    if type == "minutes":
        content = result.meeting_minutes
        filename = f"meeting-minutes-{job.id}.md"
        media_type = "text/markdown; charset=utf-8"
    elif type == "summary":
        content = result.summary
        filename = f"meeting-summary-{job.id}.md"
        media_type = "text/markdown; charset=utf-8"
    elif type == "transcript":
        content = result.speaker_transcript
        filename = f"meeting-transcript-{job.id}.txt"
        media_type = "text/plain; charset=utf-8"
    elif type == "cleaned_transcript":
        content = result.cleaned_transcript
        filename = f"meeting-cleaned-transcript-{job.id}.txt"
        media_type = "text/plain; charset=utf-8"
    else:
        content = json.dumps(_result_response(job, result).model_dump(), ensure_ascii=False, indent=2, default=str)
        filename = f"meeting-result-{job.id}.json"
        media_type = "application/json; charset=utf-8"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
