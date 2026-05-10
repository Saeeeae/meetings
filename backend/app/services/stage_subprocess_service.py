import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import Settings, settings


class StageSubprocessService:
    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings

    def run_stt(self, audio_path: str) -> dict[str, Any]:
        result = self._run_stage("stt", audio_path)
        if not isinstance(result, dict):
            raise RuntimeError("STT subprocess returned an invalid payload")
        return result

    def run_diarization(self, audio_path: str) -> list[dict]:
        result = self._run_stage("diarization", audio_path)
        if not isinstance(result, list):
            raise RuntimeError("Diarization subprocess returned an invalid payload")
        return result

    def _run_stage(self, stage: str, audio_path: str) -> Any:
        with tempfile.TemporaryDirectory(prefix=f"meeting-minutes-{stage}-") as temp_dir:
            output_path = Path(temp_dir) / "result.json"
            command = [
                sys.executable,
                "-m",
                "app.workers.stage_runner",
                stage,
                audio_path,
                str(output_path),
            ]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.settings.gpu_stage_timeout_seconds,
            )
            if completed.returncode != 0:
                stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown subprocess error"
                raise RuntimeError(f"{stage} subprocess failed: {stderr[-2000:]}")

            return json.loads(output_path.read_text(encoding="utf-8"))
