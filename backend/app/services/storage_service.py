from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.utils.file_utils import get_extension, sanitize_filename


@dataclass(frozen=True)
class StoredFile:
    original_filename: str
    stored_filename: str
    file_path: str


class StorageService:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or settings.storage_dir
        self.upload_dir = self.storage_dir / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload_file(self, upload_file: UploadFile, job_id: str) -> StoredFile:
        safe_name = sanitize_filename(upload_file.filename)
        extension = get_extension(safe_name)
        stored_filename = f"{job_id}{extension}"
        target_path = self.upload_dir / stored_filename

        total_size = 0
        chunk_size = 1024 * 1024

        try:
            with target_path.open("wb") as output_file:
                while chunk := await upload_file.read(chunk_size):
                    total_size += len(chunk)
                    if total_size > settings.max_upload_size_bytes:
                        output_file.close()
                        target_path.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File exceeds {settings.max_upload_size_mb} MB limit",
                        )
                    output_file.write(chunk)
        finally:
            await upload_file.close()

        return StoredFile(
            original_filename=safe_name,
            stored_filename=stored_filename,
            file_path=str(target_path),
        )
