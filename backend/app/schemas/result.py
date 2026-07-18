from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


DownloadType = Literal["minutes", "summary", "transcript", "cleaned_transcript", "json"]


class Segment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    speaker: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=20_000)

    @field_validator("speaker", "text", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end < self.start:
            raise ValueError("segment end must be greater than or equal to start")
        return self


class NoteMemo(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    time: float = Field(ge=0)
    text: str = Field(min_length=1, max_length=5_000)
    created_at: datetime

    @field_validator("text", mode="before")
    @classmethod
    def strip_memo_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ResultUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    segments: list[Segment] | None = Field(default=None, max_length=20_000)
    bookmarks: list[int] | None = Field(default=None, max_length=20_000)
    highlights: list[int] | None = Field(default=None, max_length=20_000)
    memos: list[NoteMemo] | None = Field(default=None, max_length=20_000)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value

    @field_validator("bookmarks", "highlights")
    @classmethod
    def normalize_indices(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(index < 0 for index in value):
            raise ValueError("segment indices must be non-negative")
        return sorted(set(value))

    @model_validator(mode="after")
    def require_update(self):
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self


class ResultResponse(BaseModel):
    job_id: str
    status: str
    title: str
    raw_transcript: str
    speaker_transcript: str
    cleaned_transcript: str
    meeting_minutes: str
    summary: str
    segments: list[Segment]
    bookmarks: list[int]
    highlights: list[int]
    memos: list[NoteMemo]
    transcript_edited_at: datetime | None = None
