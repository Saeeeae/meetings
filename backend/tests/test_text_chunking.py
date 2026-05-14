from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.utils.text_chunking import chunk_by_lines


class ChunkByLinesTests(unittest.TestCase):
    def test_empty_text_returns_single_empty_chunk(self) -> None:
        self.assertEqual(chunk_by_lines("", 100), [""])

    def test_short_text_returned_as_one_chunk(self) -> None:
        text = "[00:00:00] SPEAKER_00: 안녕하세요"
        self.assertEqual(chunk_by_lines(text, 100), [text])

    def test_text_split_on_line_boundaries(self) -> None:
        lines = [f"line {i}" for i in range(20)]
        text = "\n".join(lines)
        chunks = chunk_by_lines(text, 30)

        self.assertGreater(len(chunks), 1)
        self.assertEqual("\n".join(chunks).count("line"), 20)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 30 * 2)

    def test_oversized_single_line_is_hard_split(self) -> None:
        chunks = chunk_by_lines("x" * 250, 100)

        self.assertEqual([len(c) for c in chunks], [100, 100, 50])

    def test_line_boundaries_preserved_when_possible(self) -> None:
        text = "[00:00:00] A: 짧은 문장\n[00:00:05] B: 또 다른 문장"
        chunks = chunk_by_lines(text, 1000)

        self.assertEqual(chunks, [text])


if __name__ == "__main__":
    unittest.main()
