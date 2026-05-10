import subprocess
from pathlib import Path

from app.core.config import settings


class MediaProcessingError(RuntimeError):
    pass


class MediaService:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or settings.storage_dir
        self.processed_dir = self.storage_dir / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def preprocess(self, input_path: str, job_id: str) -> str:
        source = Path(input_path)
        if not source.exists():
            raise MediaProcessingError("Uploaded file was not found")

        output_path = self.processed_dir / f"{job_id}.wav"
        if output_path.exists() and output_path.stat().st_size > 0:
            return str(output_path)

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(output_path),
        ]

        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
        except FileNotFoundError as exc:
            raise MediaProcessingError("ffmpeg is not installed or not available in PATH") from exc

        if completed.returncode != 0:
            output_path.unlink(missing_ok=True)
            detail = completed.stderr.strip().splitlines()[-1] if completed.stderr else "unknown ffmpeg error"
            raise MediaProcessingError(f"ffmpeg failed: {detail}")

        return str(output_path)
