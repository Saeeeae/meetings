from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


class JobsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        for mod in [name for name in list(sys.modules) if name.startswith("app.")]:
            del sys.modules[mod]

        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = f"sqlite:///{self.temp_dir.name}/test.db"
        os.environ["STORAGE_DIR"] = self.temp_dir.name
        os.environ["MODELS_DIR"] = self.temp_dir.name

        from fastapi.testclient import TestClient

        app_main = importlib.import_module("app.main")
        self.client = TestClient(app_main.app)

    def tearDown(self) -> None:
        self.client.close()
        for var in ("DATABASE_URL", "STORAGE_DIR", "MODELS_DIR"):
            os.environ.pop(var, None)
        self.temp_dir.cleanup()

    def test_recent_jobs_include_filename_and_newest_first(self) -> None:
        from app.core.database import SessionLocal
        from app.models.job import Job

        now = datetime.now(timezone.utc)
        with self.client:
            db = SessionLocal()
            try:
                db.add_all(
                    [
                        Job(
                            id="older",
                            original_filename="지난 회의.m4a",
                            stored_filename="older.m4a",
                            file_path="/tmp/older.m4a",
                            status="completed",
                            progress=100,
                            current_step="completed",
                            created_at=now - timedelta(days=1),
                            updated_at=now - timedelta(days=1),
                        ),
                        Job(
                            id="newer",
                            original_filename="오늘 회의.wav",
                            stored_filename="newer.wav",
                            file_path="/tmp/newer.wav",
                            status="processing",
                            progress=35,
                            current_step="stt",
                            created_at=now,
                            updated_at=now,
                        ),
                    ]
                )
                db.commit()
            finally:
                db.close()

            response = self.client.get("/api/jobs")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([job["job_id"] for job in payload], ["newer", "older"])
        self.assertEqual(payload[0]["filename"], "오늘 회의.wav")
        self.assertEqual(payload[0]["title"], "오늘 회의")


if __name__ == "__main__":
    unittest.main()
