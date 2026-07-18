from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
for _mod in [name for name in list(sys.modules) if name.startswith("app.")]:
    del sys.modules[_mod]

from app.workers.tasks import JobProcessingError, _ensure_transcript_present


class EnsureTranscriptPresentTests(unittest.TestCase):
    def test_empty_result_raises_user_facing_error(self) -> None:
        with self.assertRaises(JobProcessingError):
            _ensure_transcript_present({"text": "", "segments": []})

    def test_whitespace_only_result_raises(self) -> None:
        with self.assertRaises(JobProcessingError):
            _ensure_transcript_present({"text": "  \n", "segments": [{"text": " "}]})

    def test_text_present_passes(self) -> None:
        _ensure_transcript_present({"text": "안녕하세요", "segments": []})

    def test_segment_text_present_passes(self) -> None:
        _ensure_transcript_present({"text": "", "segments": [{"text": "회의 시작"}]})


if __name__ == "__main__":
    unittest.main()
