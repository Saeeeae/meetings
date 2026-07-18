import logging
import subprocess
from pathlib import Path

from app.core.config import Settings, settings


logger = logging.getLogger(__name__)


class MediaProcessingError(RuntimeError):
    pass


class MediaService:
    def __init__(
        self,
        storage_dir: Path | None = None,
        app_settings: Settings = settings,
    ) -> None:
        self.settings = app_settings
        self.storage_dir = storage_dir or self.settings.storage_dir
        self.processed_dir = self.storage_dir / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def preprocess(self, input_path: str, job_id: str) -> str:
        source = Path(input_path)
        if not source.exists():
            raise MediaProcessingError("Uploaded file was not found")

        output_path = self.processed_dir / f"{job_id}.wav"
        if output_path.exists() and output_path.stat().st_size > 0:
            return str(output_path)

        filter_chain = self._build_filter_chain()
        command = ["ffmpeg", "-y", "-i", str(source)]
        if filter_chain:
            command.extend(["-af", filter_chain])
        command.extend(["-ac", "1", "-ar", "16000", str(output_path)])

        logger.info("ffmpeg preprocess for %s: filter=%s", job_id, filter_chain or "(none)")

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.settings.gpu_stage_timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise MediaProcessingError("ffmpeg is not installed or not available in PATH") from exc
        except subprocess.TimeoutExpired as exc:
            output_path.unlink(missing_ok=True)
            raise MediaProcessingError("ffmpeg preprocessing timed out") from exc

        if completed.returncode != 0:
            output_path.unlink(missing_ok=True)
            detail = completed.stderr.strip().splitlines()[-1] if completed.stderr else "unknown ffmpeg error"
            raise MediaProcessingError(f"ffmpeg failed: {detail}")

        return str(output_path)

    def has_audio_stream(self, input_path: str) -> bool:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(input_path),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60)
        except FileNotFoundError:
            logger.warning("ffprobe is not available; skipping audio content validation.")
            return True
        except subprocess.TimeoutExpired:
            return False
        return completed.returncode == 0 and "audio" in completed.stdout

    def _build_filter_chain(self) -> str:
        filters: list[str] = []

        if self.settings.audio_highpass_hz:
            filters.append(f"highpass=f={int(self.settings.audio_highpass_hz)}")

        if self.settings.audio_denoise:
            strength = max(5, int(self.settings.audio_denoise_strength_db))
            filters.append(f"afftdn=nf=-{strength}")

        if self.settings.audio_loudness_normalize:
            filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")

        return ",".join(filters)
