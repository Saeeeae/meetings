from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


class WorkerRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        for mod in [name for name in list(sys.modules) if name.startswith("app.")]:
            del sys.modules[mod]

        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = f"sqlite:///{self.temp_dir.name}/test.db"
        os.environ["STORAGE_DIR"] = self.temp_dir.name
        os.environ["MODELS_DIR"] = self.temp_dir.name
        os.environ["RECOVER_INTERRUPTED_JOBS"] = "true"

    def tearDown(self) -> None:
        for var in ("DATABASE_URL", "STORAGE_DIR", "MODELS_DIR", "RECOVER_INTERRUPTED_JOBS"):
            os.environ.pop(var, None)
        self.temp_dir.cleanup()

    def test_worker_ready_requeues_queued_and_processing_jobs(self) -> None:
        celery_module = importlib.import_module("app.workers.celery_app")
        from app.core.database import SessionLocal, init_db
        from app.models.job import Job

        init_db()
        with SessionLocal() as db:
            db.add_all(
                [
                    Job(
                        id="queued",
                        original_filename="queued.wav",
                        stored_filename="queued.wav",
                        file_path="/tmp/queued.wav",
                        status="queued",
                        progress=5,
                        current_step="uploaded",
                    ),
                    Job(
                        id="interrupted",
                        original_filename="interrupted.wav",
                        stored_filename="interrupted.wav",
                        file_path="/tmp/interrupted.wav",
                        status="processing",
                        progress=55,
                        current_step="diarization",
                    ),
                    Job(
                        id="complete",
                        original_filename="complete.wav",
                        stored_filename="complete.wav",
                        file_path="/tmp/complete.wav",
                        status="completed",
                        progress=100,
                        current_step="completed",
                    ),
                ]
            )
            db.commit()

        with patch("app.workers.tasks.process_job.delay") as delay:
            celery_module._on_worker_ready()

        self.assertEqual({call.args[0] for call in delay.call_args_list}, {"queued", "interrupted"})
        with SessionLocal() as db:
            recovered = db.get(Job, "interrupted")
            self.assertIsNotNone(recovered)
            self.assertEqual(recovered.status, "queued")
            self.assertEqual(recovered.progress, 5)
            self.assertEqual(recovered.current_step, "uploaded")
            self.assertEqual(db.get(Job, "complete").status, "completed")


if __name__ == "__main__":
    unittest.main()
