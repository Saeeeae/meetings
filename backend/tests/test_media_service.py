from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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


if __name__ == "__main__":
    unittest.main()
