from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings
from app.core.lexicon import load_lexicon
from app.services.lexicon_service import LexiconCorrectionService


class LexiconParsingTests(unittest.TestCase):
    def test_json_dictionary_loads_corrections_and_canonical_terms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "dictionary.json"
            path.write_text(
                json.dumps({"큐원": "Qwen", "브이 엘 엘 엠": "vLLM"}, ensure_ascii=False),
                encoding="utf-8",
            )

            lexicon = load_lexicon(path)

        self.assertEqual(lexicon.corrections, {"큐원": "Qwen", "브이 엘 엘 엠": "vLLM"})
        self.assertEqual(lexicon.terms, ("Qwen", "vLLM"))

    def test_legacy_terms_and_text_mappings_remain_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "dictionary.txt"
            path.write_text(
                "# 표준어 또는 오인식 매핑\n카프카\n큐 원\tQwen\n브이 엘 엘 엠 => vLLM\n",
                encoding="utf-8",
            )

            lexicon = load_lexicon(path)

        self.assertEqual(lexicon.terms, ("카프카", "Qwen", "vLLM"))
        self.assertEqual(lexicon.corrections, {"큐 원": "Qwen", "브이 엘 엘 엠": "vLLM"})

    def test_settings_exposes_prompt_mappings_and_context_terms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "dictionary.json"
            path.write_text('{"큐원": "Qwen"}', encoding="utf-8")
            settings = Settings(
                _env_file=None,
                lexicon_path=path,
                stt_context="카프카, Qwen",
            )

            self.assertEqual(settings.load_lexicon_terms(), ["카프카", "Qwen"])
            self.assertEqual(settings.load_lexicon_corrections(), {"큐원": "Qwen"})
            self.assertEqual(settings.load_lexicon_prompt_entries(), ["큐원 -> Qwen", "카프카"])


class LexiconCorrectionServiceTests(unittest.TestCase):
    def test_longest_match_wins_without_cascading_replacements(self) -> None:
        service = LexiconCorrectionService(
            {
                "클로바 노트": "클로바노트",
                "클로바": "CLOVA",
                "큐원": "Qwen",
                "Qwen": "Qwen3",
            }
        )

        corrected = service.correct_text("클로바 노트와 클로바, 큐원 모델")

        self.assertEqual(corrected, "클로바노트와 CLOVA, Qwen 모델")

    def test_ascii_alias_does_not_replace_inside_another_word(self) -> None:
        service = LexiconCorrectionService({"api": "API"})

        self.assertEqual(service.correct_text("api와 capitol의 차이"), "API와 capitol의 차이")

    def test_stt_result_segments_and_words_are_corrected_without_mutating_input(self) -> None:
        service = LexiconCorrectionService({"큐원": "Qwen"})
        original = {
            "language": "Korean",
            "text": "큐원 모델",
            "segments": [{"start": 0.0, "end": 1.0, "text": "큐원 모델"}],
            "words": [{"start": 0.0, "end": 0.4, "text": "큐원"}],
        }

        corrected = service.correct_stt_result(original)

        self.assertEqual(corrected["text"], "Qwen 모델")
        self.assertEqual(corrected["segments"][0]["text"], "Qwen 모델")
        self.assertEqual(corrected["words"][0]["text"], "Qwen")
        self.assertEqual(original["text"], "큐원 모델")


if __name__ == "__main__":
    unittest.main()
