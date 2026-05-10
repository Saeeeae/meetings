import uuid

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Result(Base):
    __tablename__ = "results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False, unique=True, index=True)
    raw_transcript: Mapped[str] = mapped_column(Text, nullable=False)
    speaker_transcript: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_transcript: Mapped[str] = mapped_column(Text, nullable=False)
    meeting_minutes: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    segments_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    job = relationship("Job", back_populates="result")
