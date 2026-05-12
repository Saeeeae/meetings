from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/meeting_minutes"
    redis_url: str = "redis://localhost:6379/0"

    storage_dir: Path = Path("./data/storage")
    models_dir: Path = Path("./models")
    max_upload_size_mb: int = 2048

    stt_provider: str = "mock"
    stt_language: str = "ko"
    faster_whisper_model: str = "small"
    faster_whisper_device: str = "auto"
    faster_whisper_compute_type: str = "int8"
    qwen_asr_model: str | None = "Qwen/Qwen3-ASR-1.7B"
    qwen_asr_forced_aligner_model: str | None = "Qwen/Qwen3-ForcedAligner-0.6B"
    qwen_asr_dtype: str | None = "bfloat16"
    qwen_asr_device_map: str | None = "cuda:0"
    qwen_asr_max_inference_batch_size: int | None = 8
    qwen_asr_max_new_tokens: int | None = 4096
    qwen_asr_return_timestamps: bool | None = True

    diarization_provider: str = "mock"
    pyannote_model: str = "pyannote/speaker-diarization-3.1"
    huggingface_token: str | None = None

    llm_provider: str = "mock"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None

    gpu_stage_subprocess: bool = True
    gpu_stage_timeout_seconds: int = 7200

    vllm_on_demand: bool = False
    vllm_model: str | None = None
    vllm_host: str = "127.0.0.1"
    vllm_port: int = 8001
    vllm_startup_timeout_seconds: int = 900
    vllm_shutdown_timeout_seconds: int = 60
    vllm_gpu_memory_utilization: float = 0.85
    vllm_dtype: str | None = "auto"
    vllm_max_model_len: int | None = None
    vllm_trust_remote_code: bool = False
    vllm_extra_args: str | None = None
    vllm_command: str | None = None
    vllm_reuse_existing: bool = True

    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    allowed_extensions: set[str] = Field(
        default_factory=lambda: {".mp3", ".wav", ".m4a", ".aac", ".flac", ".mp4", ".webm"}
    )
    allowed_mime_types: set[str] = Field(
        default_factory=lambda: {
            "audio/aac",
            "audio/flac",
            "audio/m4a",
            "audio/mp4",
            "audio/mpeg",
            "audio/wav",
            "audio/webm",
            "audio/x-m4a",
            "audio/x-wav",
            "video/mp4",
            "video/webm",
            "application/octet-stream",
        }
    )

    @field_validator(
        "qwen_asr_model",
        "qwen_asr_forced_aligner_model",
        "qwen_asr_dtype",
        "qwen_asr_device_map",
        "vllm_dtype",
        "vllm_extra_args",
        "vllm_command",
        mode="before",
    )
    @classmethod
    def empty_string_to_none_string(cls, value):
        if value == "":
            return None
        return value

    @field_validator(
        "qwen_asr_max_inference_batch_size",
        "qwen_asr_max_new_tokens",
        "vllm_max_model_len",
        mode="before",
    )
    @classmethod
    def empty_string_to_none_int(cls, value):
        if value == "":
            return None
        return value

    @field_validator("qwen_asr_return_timestamps", mode="before")
    @classmethod
    def empty_string_to_none_bool(cls, value):
        if value == "":
            return None
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def effective_llm_model(self) -> str | None:
        return self.llm_model or self.vllm_model

    @property
    def effective_llm_base_url(self) -> str | None:
        if self.llm_base_url:
            return self.llm_base_url
        if self.vllm_on_demand:
            return f"http://{self.vllm_host}:{self.vllm_port}/v1"
        return None

    @property
    def effective_vllm_model(self) -> str:
        model = self.vllm_model or self.llm_model
        if not model:
            raise RuntimeError("VLLM_MODEL or LLM_MODEL is required when VLLM_ON_DEMAND=true.")
        return model

    @property
    def vllm_health_url(self) -> str:
        base_url = self.effective_llm_base_url or f"http://{self.vllm_host}:{self.vllm_port}/v1"
        parsed = urlparse(base_url)
        path = parsed.path.rstrip("/")
        if path.endswith("/v1"):
            path = path[: -len("/v1")]
        return urlunparse(parsed._replace(path=f"{path}/health", params="", query="", fragment=""))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
