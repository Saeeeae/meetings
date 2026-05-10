import re
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str | None) -> str:
    raw_name = Path(filename or "upload").name
    safe_name = _SAFE_FILENAME_RE.sub("_", raw_name).strip("._")
    return safe_name or "upload"


def get_extension(filename: str | None) -> str:
    return Path(filename or "").suffix.lower()


def validate_upload_file(upload_file: UploadFile) -> None:
    extension = get_extension(upload_file.filename)
    if extension not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension. Allowed: {', '.join(sorted(settings.allowed_extensions))}",
        )

    content_type = upload_file.content_type or ""
    if content_type not in settings.allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported MIME type: {content_type or 'unknown'}",
        )
