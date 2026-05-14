from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.utils.file_utils import get_extension, sanitize_filename


class SanitizeFilenameTests(unittest.TestCase):
    def test_strips_path_components(self) -> None:
        self.assertEqual(sanitize_filename("/tmp/../etc/passwd"), "passwd")

    def test_preserves_ascii_safe_names(self) -> None:
        self.assertEqual(sanitize_filename("safe-name.mp3"), "safe-name.mp3")

    def test_falls_back_to_upload_name_when_empty(self) -> None:
        self.assertEqual(sanitize_filename(""), "upload")
        self.assertEqual(sanitize_filename(None), "upload")
        self.assertEqual(sanitize_filename("..."), "upload")

    def test_extension_preserved(self) -> None:
        self.assertEqual(get_extension("recording.MP3"), ".mp3")
        self.assertEqual(get_extension("noext"), "")


if __name__ == "__main__":
    unittest.main()
