from abc import ABC, abstractmethod
import inspect
import logging
import wave
from pathlib import Path
from typing import Any

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)


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
            "words": [],
        }


class QwenASRSTTService(STTService):
    ENDING_PUNCTUATION = ".?!。？！…;；"
    NO_SPACE_BEFORE = set(".,?!;:%)]}。？！…；：、")
    NO_SPACE_AFTER = set("([{")
    LANGUAGE_ALIASES = {
        "ar": "Arabic",
        "arabic": "Arabic",
        "cn": "Chinese",
        "zh": "Chinese",
        "zh-cn": "Chinese",
        "chinese": "Chinese",
        "yue": "Cantonese",
        "cantonese": "Cantonese",
        "cs": "Czech",
        "czech": "Czech",
        "da": "Danish",
        "danish": "Danish",
        "nl": "Dutch",
        "dutch": "Dutch",
        "en": "English",
        "english": "English",
        "fil": "Filipino",
        "filipino": "Filipino",
        "fi": "Finnish",
        "finnish": "Finnish",
        "fr": "French",
        "french": "French",
        "de": "German",
        "german": "German",
        "el": "Greek",
        "greek": "Greek",
        "hi": "Hindi",
        "hindi": "Hindi",
        "hu": "Hungarian",
        "hungarian": "Hungarian",
        "id": "Indonesian",
        "indonesian": "Indonesian",
        "it": "Italian",
        "italian": "Italian",
        "ja": "Japanese",
        "japanese": "Japanese",
        "jp": "Japanese",
        "ko": "Korean",
        "korean": "Korean",
        "mk": "Macedonian",
        "macedonian": "Macedonian",
        "ms": "Malay",
        "malay": "Malay",
        "fa": "Persian",
        "persian": "Persian",
        "pl": "Polish",
        "polish": "Polish",
        "pt": "Portuguese",
        "portuguese": "Portuguese",
        "ro": "Romanian",
        "romanian": "Romanian",
        "ru": "Russian",
        "russian": "Russian",
        "es": "Spanish",
        "spanish": "Spanish",
        "sv": "Swedish",
        "swedish": "Swedish",
        "th": "Thai",
        "thai": "Thai",
        "tr": "Turkish",
        "turkish": "Turkish",
        "vi": "Vietnamese",
        "vietnamese": "Vietnamese",
    }

    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        self._model = None

    def _effective_model_id(self) -> str:
        return self.settings.qwen_asr_model or "Qwen/Qwen3-ASR-1.7B"

    def _resolve_model_reference(self, model_id: str | None) -> str | None:
        if not model_id:
            return None

        model_path = Path(model_id)
        if model_path.is_absolute() and model_path.is_dir() and any(model_path.iterdir()):
            return str(model_path)

        local_path = self.settings.models_dir / "qwen-asr" / model_id.replace("/", "__")
        if local_path.exists() and any(local_path.iterdir()):
            return str(local_path)

        return model_id

    def _torch_dtype(self):
        dtype_name = self.settings.qwen_asr_dtype
        if not dtype_name:
            return None

        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("torch is required to run Qwen ASR. Install backend/requirements-ml.txt.") from exc

        normalized = dtype_name.lower().replace("-", "_")
        dtype_by_name = {
            "bf16": torch.bfloat16,
            "bfloat16": torch.bfloat16,
            "fp16": torch.float16,
            "float16": torch.float16,
            "half": torch.float16,
            "fp32": torch.float32,
            "float32": torch.float32,
        }
        if normalized == "auto":
            return None
        if normalized not in dtype_by_name:
            raise RuntimeError(f"Unsupported QWEN_ASR_DTYPE: {dtype_name}")
        return dtype_by_name[normalized]

    def _load_model(self):
        if self._model is not None:
            return self._model

        try:
            from qwen_asr import Qwen3ASRModel
        except ImportError as exc:
            raise RuntimeError("qwen-asr is not installed. Install backend/requirements-ml.txt or use STT_PROVIDER=mock.") from exc

        dtype = self._torch_dtype()
        model_kwargs: dict[str, Any] = {}
        if dtype is not None:
            model_kwargs["dtype"] = dtype
        if self.settings.qwen_asr_device_map:
            model_kwargs["device_map"] = self.settings.qwen_asr_device_map

        forced_aligner = self._resolve_model_reference(self.settings.qwen_asr_forced_aligner_model)
        forced_aligner_kwargs = None
        if forced_aligner:
            forced_aligner_kwargs = dict(model_kwargs)

        self._model = Qwen3ASRModel.from_pretrained(
            self._resolve_model_reference(self._effective_model_id()),
            forced_aligner=forced_aligner,
            forced_aligner_kwargs=forced_aligner_kwargs,
            max_inference_batch_size=self.settings.qwen_asr_max_inference_batch_size or 8,
            max_new_tokens=self.settings.qwen_asr_max_new_tokens or 4096,
            **model_kwargs,
        )
        return self._model

    def _normalize_language(self) -> str | None:
        raw_language = self.settings.stt_language
        if raw_language is None or not str(raw_language).strip():
            return None

        normalized = str(raw_language).strip().lower().replace("_", "-")
        return self.LANGUAGE_ALIASES.get(normalized, str(raw_language).strip())

    def _audio_duration(self, audio_path: str) -> float:
        try:
            with wave.open(audio_path, "rb") as audio:
                frames = audio.getnframes()
                rate = audio.getframerate()
                return float(frames / rate) if rate else 0.0
        except (EOFError, wave.Error, OSError) as exc:
            logger.warning("Failed to read audio duration from %s: %s", audio_path, exc)
            return 0.0

    def _format_segment_text(self, tokens: list[str], language: str | None) -> str:
        text = ""
        compact_language = (language or "").lower() in {"chinese", "japanese", "cantonese"}
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            if not text:
                text = token
            elif compact_language or token[0] in self.NO_SPACE_BEFORE or text[-1] in self.NO_SPACE_AFTER:
                text += token
            else:
                text += f" {token}"
        return " ".join(text.split())

    def _words_from_timestamp_items(self, items: list[Any]) -> list[dict[str, Any]]:
        words: list[dict[str, Any]] = []
        for item in items:
            token = str(getattr(item, "text", "")).strip()
            if not token:
                continue
            start = float(getattr(item, "start_time", 0.0))
            end = float(getattr(item, "end_time", start))
            words.append({"start": start, "end": end, "text": token})
        return words

    def _segments_from_timestamp_items(self, items: list[Any], language: str | None) -> list[dict[str, Any]]:
        segments: list[dict[str, Any]] = []
        current_tokens: list[str] = []
        current_start: float | None = None
        current_end: float | None = None

        def flush() -> None:
            nonlocal current_tokens, current_start, current_end
            text = self._format_segment_text(current_tokens, language)
            if text and current_start is not None and current_end is not None:
                segments.append({"start": float(current_start), "end": float(current_end), "text": text})
            current_tokens = []
            current_start = None
            current_end = None

        for item in items:
            token = str(getattr(item, "text", "")).strip()
            start = float(getattr(item, "start_time", 0.0))
            end = float(getattr(item, "end_time", start))
            if not token:
                continue

            if current_tokens and current_end is not None and start - current_end >= 0.8:
                flush()

            if current_start is None:
                current_start = start

            current_tokens.append(token)
            current_end = end

            if token[-1:] in self.ENDING_PUNCTUATION or (current_start is not None and end - current_start >= 8.0):
                flush()

        flush()
        return segments

    def _extract_items(self, result: Any) -> list[Any]:
        timestamps = getattr(result, "time_stamps", None)
        return list(getattr(timestamps, "items", []) or [])

    def _segments_from_result(self, result: Any, audio_path: str) -> list[dict[str, Any]]:
        items = self._extract_items(result)
        if items:
            return self._segments_from_timestamp_items(items, getattr(result, "language", None))

        text = str(getattr(result, "text", "") or "").strip()
        if not text:
            return []
        return [{"start": 0.0, "end": self._audio_duration(audio_path), "text": text}]

    def transcribe(self, audio_path: str) -> dict[str, Any]:
        if not Path(audio_path).exists():
            raise RuntimeError("Audio file was not found for STT")

        model = self._load_model()
        language = self._normalize_language()
        return_timestamps = self.settings.qwen_asr_return_timestamps is not False and bool(
            self.settings.qwen_asr_forced_aligner_model
        )
        call_kwargs: dict[str, Any] = {
            "audio": audio_path,
            "language": language,
            "return_time_stamps": return_timestamps,
        }
        lexicon_terms = self.settings.load_lexicon_terms()
        if lexicon_terms:
            params = inspect.signature(model.transcribe).parameters
            context_text = ", ".join(lexicon_terms)
            if "context" in params:
                call_kwargs["context"] = context_text
            elif "hotwords" in params:
                call_kwargs["hotwords"] = context_text
        results = model.transcribe(**call_kwargs)
        if not results:
            logger.warning("Qwen ASR returned no results for %s", audio_path)
            return {"language": language or "unknown", "text": "", "segments": []}

        result = results[0]
        text = str(getattr(result, "text", "") or "").strip()
        items = self._extract_items(result)
        words = self._words_from_timestamp_items(items)
        segments = (
            self._segments_from_timestamp_items(items, getattr(result, "language", None))
            if items
            else self._segments_from_result(result, audio_path)
        )
        return {
            "language": getattr(result, "language", language or "unknown"),
            "text": text,
            "segments": segments,
            "words": words,
        }


def get_stt_service(app_settings: Settings = settings) -> STTService:
    provider = app_settings.stt_provider.lower()
    if provider == "mock":
        return MockSTTService()
    if provider in {"qwen_asr", "qwen-asr", "qwen3_asr", "qwen3-asr"}:
        return QwenASRSTTService(app_settings)
    raise RuntimeError(
        f"Unsupported STT_PROVIDER: {app_settings.stt_provider}. "
        "Supported providers: qwen_asr, mock."
    )
