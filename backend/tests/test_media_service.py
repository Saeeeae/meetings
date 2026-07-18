from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings
from app.services.media_service import MediaService


def _service(**overrides) -> MediaService:
    with TemporaryDirectory() as tmp:
        s = Settings(_env_file=None, storage_dir=Path(tmp), **overrides)
        return MediaService(storage_dir=Path(tmp), app_settings=s)


class MediaFilterChainTests(unittest.TestCase):
    def test_default_chain_has_highpass_and_loudnorm(self) -> None:
        chain = _service()._build_filter_chain()
        self.assertIn("highpass=f=80", chain)
        self.assertIn("loudnorm", chain)
        self.assertNotIn("afftdn", chain)

    def test_denoise_enabled_appends_afftdn(self) -> None:
        chain = _service(audio_denoise=True, audio_denoise_strength_db=15)._build_filter_chain()
        self.assertIn("afftdn=nf=-15", chain)

    def test_all_disabled_yields_empty_chain(self) -> None:
        chain = _service(
            audio_loudness_normalize=False,
            audio_highpass_hz=None,
            audio_denoise=False,
        )._build_filter_chain()
        self.assertEqual(chain, "")

    def test_highpass_only(self) -> None:
        chain = _service(
            audio_loudness_normalize=False,
            audio_highpass_hz=120,
            audio_denoise=False,
        )._build_filter_chain()
        self.assertEqual(chain, "highpass=f=120")


class PreprocessAtomicWriteTests(unittest.TestCase):
    def test_success_renames_partial_to_final(self) -> None:
        with TemporaryDirectory() as tmp:
            from app.core.config import Settings

            source = Path(tmp) / "input.mp3"
            source.write_bytes(b"fake-audio")
            service = MediaService(
                storage_dir=Path(tmp),
                app_settings=Settings(_env_file=None, storage_dir=Path(tmp)),
            )

            def fake_ffmpeg(command, **kwargs):
                Path(command[-1]).write_bytes(b"fake-wav")
                return MagicMock(returncode=0, stderr="")

            with patch("app.services.media_service.subprocess.run", side_effect=fake_ffmpeg):
                output = service.preprocess(str(source), "job-1")

            self.assertTrue(Path(output).name == "job-1.wav" and Path(output).exists())
            self.assertFalse((Path(tmp) / "processed" / "job-1.partial.wav").exists())

    def test_failure_removes_partial_file(self) -> None:
        with TemporaryDirectory() as tmp:
            from app.core.config import Settings

            source = Path(tmp) / "input.mp3"
            source.write_bytes(b"fake-audio")
            service = MediaService(
                storage_dir=Path(tmp),
                app_settings=Settings(_env_file=None, storage_dir=Path(tmp)),
            )

            def failing_ffmpeg(command, **kwargs):
                Path(command[-1]).write_bytes(b"partial")
                return MagicMock(returncode=1, stderr="boom")

            with patch("app.services.media_service.subprocess.run", side_effect=failing_ffmpeg):
                with self.assertRaises(Exception):
                    service.preprocess(str(source), "job-2")

            processed = Path(tmp) / "processed"
            self.assertFalse((processed / "job-2.wav").exists())
            self.assertFalse((processed / "job-2.partial.wav").exists())


class AudioStreamProbeTests(unittest.TestCase):
    def test_audio_stream_detected(self) -> None:
        completed = MagicMock(returncode=0, stdout="audio\n")
        with patch("app.services.media_service.subprocess.run", return_value=completed):
            self.assertTrue(_service().has_audio_stream("/tmp/meeting.wav"))

    def test_no_audio_stream_rejected(self) -> None:
        completed = MagicMock(returncode=0, stdout="")
        with patch("app.services.media_service.subprocess.run", return_value=completed):
            self.assertFalse(_service().has_audio_stream("/tmp/not-audio.pdf"))

    def test_missing_ffprobe_skips_validation(self) -> None:
        with patch(
            "app.services.media_service.subprocess.run", side_effect=FileNotFoundError
        ):
            self.assertTrue(_service().has_audio_stream("/tmp/meeting.wav"))


if __name__ == "__main__":
    unittest.main()
