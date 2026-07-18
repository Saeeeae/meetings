from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings


class ProductionConfigurationTests(unittest.TestCase):
    def test_development_allows_mock_providers(self) -> None:
        Settings(_env_file=None, app_env="development").validate_runtime_configuration()

    def test_unsafe_production_configuration_is_rejected(self) -> None:
        settings = Settings(
            _env_file=None,
            app_env="production",
            api_key=None,
            stt_provider="qwen_asr",
            diarization_provider="mock",
            llm_provider="mock",
            cors_origins="http://localhost:5173",
        )

        with self.assertRaisesRegex(RuntimeError, "Unsafe production configuration"):
            settings.validate_runtime_configuration()

    def test_non_https_production_origin_is_rejected(self) -> None:
        settings = Settings(
            _env_file=None,
            app_env="production",
            api_key="secret",
            stt_provider="qwen_asr",
            diarization_provider="pyannote",
            llm_provider="openai",
            cors_origins="http://notes.example.com",
        )

        with self.assertRaisesRegex(RuntimeError, "HTTPS origins"):
            settings.validate_runtime_configuration()

    def test_production_accepts_real_providers_and_https_origin(self) -> None:
        settings = Settings(
            _env_file=None,
            app_env="production",
            api_key="secret",
            stt_provider="qwen_asr",
            diarization_provider="pyannote",
            llm_provider="openai",
            cors_origins="https://notes.example.com",
        )

        settings.validate_runtime_configuration()


if __name__ == "__main__":
    unittest.main()
