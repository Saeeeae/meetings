from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.core.config import Settings, settings


class STTService(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> dict[str, Any]:
        raise NotImplementedError


class MockSTTService(STTService):
    def transcribe(self, audio_path: str) -> dict[str, Any]:
        return {
            "language": "ko",
            "text": (
                "안녕하세요. 오늘 회의를 시작하겠습니다. "
                "지난주 진행 상황을 공유드리겠습니다. "
                "API 구현은 완료되었고 프론트엔드 연동이 남아 있습니다. "
                "다음 주까지 업로드 안정성과 결과 다운로드를 검증하겠습니다."
            ),
            "segments": [
                {"start": 0.0, "end": 4.0, "text": "안녕하세요. 오늘 회의를 시작하겠습니다."},
                {"start": 4.0, "end": 9.0, "text": "지난주 진행 상황을 공유드리겠습니다."},
                {"start": 9.0, "end": 15.0, "text": "API 구현은 완료되었고 프론트엔드 연동이 남아 있습니다."},
                {"start": 15.0, "end": 22.0, "text": "다음 주까지 업로드 안정성과 결과 다운로드를 검증하겠습니다."},
            ],
        }


class FasterWhisperSTTService(STTService):
    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        self._model = None

    def _resolve_model_reference(self) -> str:
        model_name = self.settings.faster_whisper_model
        local_path = self.settings.models_dir / "faster-whisper" / model_name
        if local_path.exists() and any(local_path.iterdir()):
            return str(local_path)
        return model_name

    def _load_model(self):
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Install backend/requirements-ml.txt or use STT_PROVIDER=mock."
            ) from exc

        self.settings.models_dir.mkdir(parents=True, exist_ok=True)
        download_root = self.settings.models_dir / "faster-whisper"
        download_root.mkdir(parents=True, exist_ok=True)
        self._model = WhisperModel(
            self._resolve_model_reference(),
            device=self.settings.faster_whisper_device,
            compute_type=self.settings.faster_whisper_compute_type,
            download_root=str(download_root),
        )
        return self._model

    def transcribe(self, audio_path: str) -> dict[str, Any]:
        if not Path(audio_path).exists():
            raise RuntimeError("Audio file was not found for STT")

        model = self._load_model()
        language = self.settings.stt_language or None
        segments, info = model.transcribe(audio_path, language=language, vad_filter=True)
        normalized_segments = [
            {"start": float(segment.start), "end": float(segment.end), "text": segment.text.strip()}
            for segment in segments
        ]
        text = " ".join(segment["text"] for segment in normalized_segments).strip()
        return {"language": getattr(info, "language", language or "unknown"), "text": text, "segments": normalized_segments}


def get_stt_service(app_settings: Settings = settings) -> STTService:
    provider = app_settings.stt_provider.lower()
    if provider == "mock":
        return MockSTTService()
    if provider in {"faster_whisper", "faster-whisper"}:
        return FasterWhisperSTTService(app_settings)
    raise RuntimeError(f"Unsupported STT_PROVIDER: {app_settings.stt_provider}")
