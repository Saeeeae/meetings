from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "download_models.py"
SPEC = importlib.util.spec_from_file_location("download_models", SCRIPT_PATH)
download_models = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(download_models)


class DownloadModelsTests(unittest.TestCase):
    def test_qwen_asr_download_uses_huggingface_model_names_and_cache_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            calls = []

            def fake_snapshot_download(repo_id: str, target: Path, token: str | None = None) -> None:
                calls.append((repo_id, target, token))

            with patch.dict(
                os.environ,
                {
                    "QWEN_ASR_MODEL": "Qwen/Qwen3-ASR-1.7B",
                    "QWEN_ASR_FORCED_ALIGNER_MODEL": "Qwen/Qwen3-ForcedAligner-0.6B",
                    "HUGGINGFACE_TOKEN": "hf_test",
                },
                clear=True,
            ), patch.object(download_models, "snapshot_download", side_effect=fake_snapshot_download):
                download_models.download_qwen_asr_model(Path(temp_dir))

            self.assertEqual(
                calls,
                [
                    (
                        "Qwen/Qwen3-ASR-1.7B",
                        Path(temp_dir) / "qwen-asr" / "Qwen__Qwen3-ASR-1.7B",
                        "hf_test",
                    ),
                    (
                        "Qwen/Qwen3-ForcedAligner-0.6B",
                        Path(temp_dir) / "qwen-asr" / "Qwen__Qwen3-ForcedAligner-0.6B",
                        "hf_test",
                    ),
                ],
            )

    def test_qwen_asr_download_skips_existing_cached_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "qwen-asr" / "Qwen__Qwen3-ASR-1.7B"
            target.mkdir(parents=True)
            (target / "config.json").write_text("{}", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "QWEN_ASR_MODEL": "Qwen/Qwen3-ASR-1.7B",
                    "QWEN_ASR_FORCED_ALIGNER_MODEL": "",
                },
                clear=True,
            ), patch.object(download_models, "snapshot_download") as snapshot_download:
                download_models.download_qwen_asr_model(Path(temp_dir))

            snapshot_download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
