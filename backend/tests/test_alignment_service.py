from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.alignment_service import AlignmentService


class AlignmentServiceTests(unittest.TestCase):
    def test_segment_assigned_to_majority_speaker_by_overlap(self) -> None:
        stt = [{"start": 0.0, "end": 5.0, "text": "hello"}]
        diar = [
            {"start": 0.0, "end": 4.0, "speaker": "A"},
            {"start": 4.0, "end": 6.0, "speaker": "B"},
        ]

        aligned = AlignmentService().align(stt, diar)

        self.assertEqual(aligned[0]["speaker"], "A")

    def test_unknown_when_no_overlap(self) -> None:
        stt = [{"start": 10.0, "end": 12.0, "text": "x"}]
        diar = [{"start": 0.0, "end": 5.0, "speaker": "A"}]

        aligned = AlignmentService().align(stt, diar)

        self.assertEqual(aligned[0]["speaker"], "UNKNOWN")

    def test_handles_missing_text_and_speaker_gracefully(self) -> None:
        stt = [{"start": 0.0, "end": 1.0}]
        diar = [{"start": 0.0, "end": 1.0}]

        aligned = AlignmentService().align(stt, diar)

        self.assertEqual(aligned[0]["text"], "")
        self.assertEqual(aligned[0]["speaker"], "UNKNOWN")

    def test_segment_split_at_speaker_boundary_when_no_dominant_speaker(self) -> None:
        stt = [{"start": 0.0, "end": 10.0, "text": "내가 말했고 너가 답했다"}]
        diar = [
            {"start": 0.0, "end": 5.0, "speaker": "A"},
            {"start": 5.0, "end": 10.0, "speaker": "B"},
        ]

        aligned = AlignmentService().align(stt, diar)

        self.assertEqual(len(aligned), 2)
        self.assertEqual(aligned[0]["speaker"], "A")
        self.assertEqual(aligned[1]["speaker"], "B")
        self.assertEqual(aligned[0]["end"], 5.0)
        self.assertEqual(aligned[1]["start"], 5.0)
        rejoined = " ".join(part["text"] for part in aligned)
        self.assertEqual(rejoined, "내가 말했고 너가 답했다")

    def test_dominant_speaker_keeps_segment_intact(self) -> None:
        stt = [{"start": 0.0, "end": 10.0, "text": "긴 발화 내용입니다"}]
        diar = [
            {"start": 0.0, "end": 9.0, "speaker": "A"},
            {"start": 9.0, "end": 10.0, "speaker": "B"},
        ]

        aligned = AlignmentService().align(stt, diar)

        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0]["speaker"], "A")
        self.assertEqual(aligned[0]["text"], "긴 발화 내용입니다")

    def test_consecutive_same_speaker_turns_merged(self) -> None:
        stt = [{"start": 0.0, "end": 10.0, "text": "AAAA BBBB"}]
        diar = [
            {"start": 0.0, "end": 3.0, "speaker": "A"},
            {"start": 3.0, "end": 5.0, "speaker": "A"},
            {"start": 5.0, "end": 10.0, "speaker": "B"},
        ]

        aligned = AlignmentService().align(stt, diar)

        self.assertEqual(len(aligned), 2)
        self.assertEqual(aligned[0]["speaker"], "A")
        self.assertEqual(aligned[1]["speaker"], "B")

    def test_word_level_split_preserves_exact_words(self) -> None:
        stt = [{"start": 0.0, "end": 10.0, "text": "내가 말했고 너가 답했다"}]
        diar = [
            {"start": 0.0, "end": 5.0, "speaker": "A"},
            {"start": 5.0, "end": 10.0, "speaker": "B"},
        ]
        words = [
            {"start": 0.5, "end": 1.5, "text": "내가"},
            {"start": 1.6, "end": 3.0, "text": "말했고"},
            {"start": 5.5, "end": 7.0, "text": "너가"},
            {"start": 7.1, "end": 9.0, "text": "답했다"},
        ]

        aligned = AlignmentService().align(stt, diar, words=words)

        self.assertEqual(len(aligned), 2)
        self.assertEqual(aligned[0]["speaker"], "A")
        self.assertEqual(aligned[0]["text"], "내가 말했고")
        self.assertEqual(aligned[1]["speaker"], "B")
        self.assertEqual(aligned[1]["text"], "너가 답했다")

    def test_word_level_emits_three_pieces_when_speaker_alternates(self) -> None:
        stt = [{"start": 0.0, "end": 12.0, "text": "A1 B1 A2"}]
        diar = [
            {"start": 0.0, "end": 4.0, "speaker": "A"},
            {"start": 4.0, "end": 8.0, "speaker": "B"},
            {"start": 8.0, "end": 12.0, "speaker": "A"},
        ]
        words = [
            {"start": 0.5, "end": 1.5, "text": "A1"},
            {"start": 4.5, "end": 6.0, "text": "B1"},
            {"start": 9.0, "end": 11.0, "text": "A2"},
        ]

        aligned = AlignmentService().align(stt, diar, words=words)

        self.assertEqual([p["speaker"] for p in aligned], ["A", "B", "A"])
        self.assertEqual([p["text"] for p in aligned], ["A1", "B1", "A2"])

    def test_word_level_fallback_when_words_empty(self) -> None:
        stt = [{"start": 0.0, "end": 10.0, "text": "내가 말했고 너가 답했다"}]
        diar = [
            {"start": 0.0, "end": 5.0, "speaker": "A"},
            {"start": 5.0, "end": 10.0, "speaker": "B"},
        ]

        aligned_no_words = AlignmentService().align(stt, diar, words=[])
        aligned_legacy = AlignmentService().align(stt, diar)

        self.assertEqual(aligned_no_words, aligned_legacy)
        self.assertEqual(len(aligned_no_words), 2)


if __name__ == "__main__":
    unittest.main()
