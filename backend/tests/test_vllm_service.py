from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings
from app.services.vllm_service import OnDemandVLLM


def _settings(tmp: str, **overrides) -> Settings:
    values = {
        "storage_dir": Path(tmp),
        "vllm_on_demand": True,
        "llm_provider": "openai_compatible",
        "vllm_model": "test/model",
        "vllm_startup_timeout_seconds": 0,
        "vllm_shutdown_timeout_seconds": 1,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class OnDemandVLLMEnterFailureTests(unittest.TestCase):
    def test_startup_timeout_terminates_spawned_process(self) -> None:
        fake_process = MagicMock()
        fake_process.poll.return_value = None

        with TemporaryDirectory() as tmp:
            manager = OnDemandVLLM(_settings(tmp))
            with (
                patch.object(OnDemandVLLM, "_health_check", return_value=False),
                patch("app.services.vllm_service.subprocess.Popen", return_value=fake_process),
            ):
                with self.assertRaises(RuntimeError):
                    manager.__enter__()

        fake_process.terminate.assert_called_once()
        self.assertIsNone(manager.log_file)

    def test_early_exit_of_vllm_process_still_reaps_process(self) -> None:
        fake_process = MagicMock()
        fake_process.poll.return_value = 1

        with TemporaryDirectory() as tmp:
            manager = OnDemandVLLM(_settings(tmp, vllm_startup_timeout_seconds=5))
            with (
                patch.object(OnDemandVLLM, "_health_check", return_value=False),
                patch("app.services.vllm_service.subprocess.Popen", return_value=fake_process),
            ):
                with self.assertRaises(RuntimeError):
                    manager.__enter__()

        fake_process.terminate.assert_called_once()

    def test_reuse_rejected_when_port_serves_non_llm_service(self) -> None:
        with TemporaryDirectory() as tmp:
            manager = OnDemandVLLM(_settings(tmp))
            with (
                patch.object(OnDemandVLLM, "_health_check", return_value=True),
                patch.object(OnDemandVLLM, "_serves_openai_models", return_value=False),
            ):
                with self.assertRaises(RuntimeError):
                    manager.__enter__()

    def test_reuse_allowed_when_existing_server_is_openai_compatible(self) -> None:
        with TemporaryDirectory() as tmp:
            manager = OnDemandVLLM(_settings(tmp))
            with (
                patch.object(OnDemandVLLM, "_health_check", return_value=True),
                patch.object(OnDemandVLLM, "_serves_openai_models", return_value=True),
            ):
                self.assertIs(manager.__enter__(), manager)
            self.assertIsNone(manager.process)


if __name__ == "__main__":
    unittest.main()
