from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings
from app.services.llm_service import LLMService


class _RecordingLLM(LLMService):
    def __init__(self, app_settings: Settings, language: str | None = None) -> None:
        super().__init__(app_settings, language)
        self.calls: list[tuple[str, str]] = []

    def _run_prompt(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return f"OUT[{user_prompt[:24]}]"


def _settings(max_chars: int = 100, **overrides: object) -> Settings:
    return Settings(_env_file=None, llm_max_input_chars=max_chars, **overrides)


class LLMServiceChunkingTests(unittest.TestCase):
    def test_cleanup_single_chunk_one_call(self) -> None:
        llm = _RecordingLLM(_settings(max_chars=10_000))

        result = llm.cleanup_transcript("[00:00:00] A: 한 줄짜리 발화")

        self.assertEqual(len(llm.calls), 1)
        self.assertTrue(result.startswith("OUT["))

    def test_cleanup_chunks_per_call(self) -> None:
        llm = _RecordingLLM(_settings(max_chars=2_000))
        lines = "\n".join(f"[00:00:{i:02d}] A: 발화 내용 {i}" for i in range(200))

        llm.cleanup_transcript(lines)

        self.assertGreater(len(llm.calls), 1)

    def test_minutes_map_reduce_emits_extra_merge_call(self) -> None:
        llm = _RecordingLLM(_settings(max_chars=2_000))
        long_text = "\n".join(f"[00:00:{i:02d}] A: 문장 {i}" for i in range(500))

        llm.generate_minutes(long_text)

        self.assertGreaterEqual(len(llm.calls), 3)
        self.assertIn("통합", llm.calls[-1][0])

    def test_summary_uses_cleaned_transcript_directly(self) -> None:
        llm = _RecordingLLM(_settings(max_chars=10_000))

        llm.generate_summary("[00:00:00] A: 짧은 발화")

        self.assertEqual(len(llm.calls), 1)
        self.assertIn("핵심 요약", llm.calls[0][0])

    def test_lexicon_clause_attached_to_cleanup_system_prompt(self) -> None:
        llm = _RecordingLLM(_settings(max_chars=10_000, stt_context="카프카, 프로비저닝"))

        llm.cleanup_transcript("[00:00:00] A: 안녕")

        system_prompt, _ = llm.calls[0]
        self.assertIn("카프카", system_prompt)
        self.assertIn("프로비저닝", system_prompt)

    def test_english_language_switches_prompt_set(self) -> None:
        llm = _RecordingLLM(_settings(max_chars=10_000), language="en")

        llm.generate_summary("[00:00:00] A: hello, this is a short utterance.")

        self.assertIn("Key Summary", llm.calls[0][0])
        self.assertNotIn("핵심 요약", llm.calls[0][0])

    def test_korean_language_remains_default(self) -> None:
        llm = _RecordingLLM(_settings(max_chars=10_000))

        llm.generate_minutes("[00:00:00] A: 짧은 발화")

        self.assertIn("회의 개요", llm.calls[0][0])

    def test_language_hint_overrides_settings(self) -> None:
        llm_en = _RecordingLLM(_settings(max_chars=10_000, stt_language="ko"), language="English")
        llm_en.generate_minutes("hi")
        self.assertIn("Overview", llm_en.calls[0][0])


if __name__ == "__main__":
    unittest.main()
