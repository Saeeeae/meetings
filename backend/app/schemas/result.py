from typing import Literal

from pydantic import BaseModel


DownloadType = Literal["minutes", "summary", "transcript", "cleaned_transcript", "json"]


class Segment(BaseModel):
    start: float
    end: float
    speaker: str
    text: str


class ResultResponse(BaseModel):
    job_id: str
    status: str
    raw_transcript: str
    speaker_transcript: str
    cleaned_transcript: str
    meeting_minutes: str
    summary: str
    segments: list[Segment]
