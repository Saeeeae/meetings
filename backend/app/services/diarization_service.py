from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import Settings, settings


class DiarizationService(ABC):
    @abstractmethod
    def diarize(self, audio_path: str) -> list[dict]:
        raise NotImplementedError


class MockDiarizationService(DiarizationService):
    def diarize(self, audio_path: str) -> list[dict]:
        return [
            {"start": 0.0, "end": 7.0, "speaker": "SPEAKER_00"},
            {"start": 7.0, "end": 13.0, "speaker": "SPEAKER_01"},
            {"start": 13.0, "end": 24.0, "speaker": "SPEAKER_00"},
        ]


class PyannoteDiarizationService(DiarizationService):
    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        self._pipeline = None

    def _local_model_path(self) -> Path:
        safe_name = self.settings.pyannote_model.replace("/", "__")
        return self.settings.models_dir / "pyannote" / safe_name

    def _resolve_model_reference(self) -> str:
        local_path = self._local_model_path()
        if local_path.exists() and any(local_path.iterdir()):
            return str(local_path)
        return self.settings.pyannote_model

    def _load_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline

        try:
            from pyannote.audio import Pipeline
        except ImportError as exc:
            raise RuntimeError(
                "pyannote.audio is not installed. Install backend/requirements-ml.txt or use DIARIZATION_PROVIDER=mock."
            ) from exc

        model_reference = self._resolve_model_reference()
        local_model = Path(model_reference).exists()
        if not local_model and not self.settings.huggingface_token:
            raise RuntimeError("HUGGINGFACE_TOKEN is required for pyannote diarization model download/loading.")

        self._pipeline = Pipeline.from_pretrained(
            model_reference,
            use_auth_token=None if local_model else self.settings.huggingface_token,
        )
        return self._pipeline

    def diarize(self, audio_path: str) -> list[dict]:
        if not Path(audio_path).exists():
            raise RuntimeError("Audio file was not found for diarization")

        pipeline = self._load_pipeline()
        diarize_kwargs: dict = {}
        if self.settings.pyannote_num_speakers is not None:
            diarize_kwargs["num_speakers"] = self.settings.pyannote_num_speakers
        else:
            if self.settings.pyannote_min_speakers is not None:
                diarize_kwargs["min_speakers"] = self.settings.pyannote_min_speakers
            if self.settings.pyannote_max_speakers is not None:
                diarize_kwargs["max_speakers"] = self.settings.pyannote_max_speakers
        diarization = pipeline(audio_path, **diarize_kwargs)
        segments: list[dict] = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({"start": float(turn.start), "end": float(turn.end), "speaker": str(speaker)})
        return segments


def get_diarization_service(app_settings: Settings = settings) -> DiarizationService:
    provider = app_settings.diarization_provider.lower()
    if provider == "mock":
        return MockDiarizationService()
    if provider == "pyannote":
        return PyannoteDiarizationService(app_settings)
    raise RuntimeError(f"Unsupported DIARIZATION_PROVIDER: {app_settings.diarization_provider}")
