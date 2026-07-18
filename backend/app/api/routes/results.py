import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import Job
from app.models.result import Result
from app.schemas.result import DownloadType, ResultResponse, ResultUpdateRequest
from app.services.minutes_service import MinutesService

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
        title=(job.title or "").strip() or Path(job.original_filename).stem or "제목 없는 노트",
        raw_transcript=result.raw_transcript,
        speaker_transcript=result.speaker_transcript,
        cleaned_transcript=result.cleaned_transcript,
        meeting_minutes=result.meeting_minutes,
        summary=result.summary,
        segments=result.segments_json,
        bookmarks=list(result.bookmarks_json or []),
        highlights=list(result.highlights_json or []),
        memos=list(result.memos_json or []),
        transcript_edited_at=result.transcript_edited_at,
    )


@router.get("/results/{job_id}", response_model=ResultResponse)
def get_result(job_id: str, db: Session = Depends(get_db)) -> ResultResponse:
    job, result = _get_completed_job_and_result(db, job_id)
    return _result_response(job, result)


@router.patch("/results/{job_id}", response_model=ResultResponse)
def update_result(
    job_id: str,
    update: ResultUpdateRequest,
    db: Session = Depends(get_db),
) -> ResultResponse:
    job, result = _get_completed_job_and_result(db, job_id)

    if "title" in update.model_fields_set:
        job.title = update.title

    if update.segments is not None:
        current_segments = list(result.segments_json or [])
        if len(update.segments) != len(current_segments):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="구간 수는 변경할 수 없습니다.",
            )

        updated_segments = [segment.model_dump() for segment in update.segments]
        for current, changed in zip(current_segments, updated_segments, strict=True):
            if (
                abs(float(current.get("start", 0.0)) - float(changed["start"])) > 0.01
                or abs(float(current.get("end", 0.0)) - float(changed["end"])) > 0.01
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="구간의 시작·종료 시간은 변경할 수 없습니다.",
                )

        result.segments_json = updated_segments
        result.raw_transcript = " ".join(segment["text"] for segment in updated_segments).strip()
        result.speaker_transcript = MinutesService().build_speaker_transcript(updated_segments)
        result.cleaned_transcript = result.speaker_transcript
        result.transcript_edited_at = datetime.now(timezone.utc)

    segment_count = len(result.segments_json or [])
    if update.bookmarks is not None:
        if any(index >= segment_count for index in update.bookmarks):
            raise HTTPException(status_code=422, detail="존재하지 않는 구간의 북마크가 포함되어 있습니다.")
        result.bookmarks_json = update.bookmarks
    if update.highlights is not None:
        if any(index >= segment_count for index in update.highlights):
            raise HTTPException(status_code=422, detail="존재하지 않는 구간의 하이라이트가 포함되어 있습니다.")
        result.highlights_json = update.highlights
    if update.memos is not None:
        result.memos_json = [memo.model_dump(mode="json") for memo in update.memos]

    db.commit()
    db.refresh(job)
    db.refresh(result)
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
