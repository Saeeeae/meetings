from __future__ import annotations

import sys
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings
from app.services.stt_service import QwenASRSTTService, get_stt_service


class QwenASRSTTServiceTests(unittest.TestCase):
    def make_settings(self, **overrides) -> Settings:
        values = {
            "stt_provider": "qwen_asr",
            "stt_language": "ko",
            "models_dir": Path("/tmp/models"),
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)

    def test_provider_alias_resolves_to_qwen_asr_service(self) -> None:
        service = get_stt_service(self.make_settings(stt_provider="qwen-asr"))

        self.assertIsInstance(service, QwenASRSTTService)

    def test_language_mapping(self) -> None:
        self.assertEqual(QwenASRSTTService(self.make_settings(stt_language="ko"))._normalize_language(), "Korean")
        self.assertEqual(QwenASRSTTService(self.make_settings(stt_language="en"))._normalize_language(), "English")
        self.assertIsNone(QwenASRSTTService(self.make_settings(stt_language=""))._normalize_language())

    def test_timestamp_items_are_grouped_into_segments(self) -> None:
        service = QwenASRSTTService(self.make_settings())
        items = [
            SimpleNamespace(text="안녕하세요", start_time=0.0, end_time=0.5),
            SimpleNamespace(text="오늘", start_time=0.6, end_time=0.9),
            SimpleNamespace(text="회의입니다.", start_time=1.0, end_time=1.6),
            SimpleNamespace(text="다음", start_time=2.7, end_time=3.0),
            SimpleNamespace(text="안건입니다", start_time=3.1, end_time=3.5),
        ]

        segments = service._segments_from_timestamp_items(items, "Korean")

        self.assertEqual(
            segments,
            [
                {"start": 0.0, "end": 1.6, "text": "안녕하세요 오늘 회의입니다."},
                {"start": 2.7, "end": 3.5, "text": "다음 안건입니다"},
            ],
        )

    def test_missing_timestamps_falls_back_to_single_segment(self) -> None:
        service = QwenASRSTTService(self.make_settings())
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            with wave.open(audio_file.name, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(b"\0\0" * 16000)

            result = SimpleNamespace(language="Korean", text="테스트 문장입니다.", time_stamps=None)

            self.assertEqual(
                service._segments_from_result(result, audio_file.name),
                [{"start": 0.0, "end": 1.0, "text": "테스트 문장입니다."}],
            )


if __name__ == "__main__":
    unittest.main()
