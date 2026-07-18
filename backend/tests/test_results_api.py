from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


class ResultsApiTests(unittest.TestCase):
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
        self.client.__enter__()
        self._seed_completed_job()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        for var in ("DATABASE_URL", "STORAGE_DIR", "MODELS_DIR"):
            os.environ.pop(var, None)
        self.temp_dir.cleanup()

    def _seed_completed_job(self) -> None:
        from app.core.database import SessionLocal
        from app.models.job import Job
        from app.models.result import Result

        upload_path = Path(self.temp_dir.name) / "uploads" / "editable.wav"
        processed_path = Path(self.temp_dir.name) / "processed" / "editable.wav"
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        upload_path.write_bytes(b"upload")
        processed_path.write_bytes(b"processed")

        with SessionLocal() as db:
            db.add(
                Job(
                    id="editable",
                    original_filename="고객 인터뷰.wav",
                    stored_filename="editable.wav",
                    file_path=str(upload_path),
                    status="completed",
                    progress=100,
                    current_step="completed",
                )
            )
            db.add(
                Result(
                    job_id="editable",
                    raw_transcript="원래 문장 다음 문장",
                    speaker_transcript="[00:00:00] SPEAKER_00: 원래 문장",
                    cleaned_transcript="[00:00:00] SPEAKER_00: 원래 문장",
                    meeting_minutes="회의록",
                    summary="요약",
                    segments_json=[
                        {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "text": "원래 문장"},
                        {"start": 1.0, "end": 2.0, "speaker": "SPEAKER_01", "text": "다음 문장"},
                    ],
                )
            )
            db.commit()

    def test_result_edits_and_annotations_are_persisted(self) -> None:
        response = self.client.patch(
            "/api/results/editable",
            json={
                "title": "수정된 고객 인터뷰",
                "segments": [
                    {"start": 0.0, "end": 1.0, "speaker": "김민수", "text": "수정한 문장"},
                    {"start": 1.0, "end": 2.0, "speaker": "담당자", "text": "다음 문장"},
                ],
                "bookmarks": [1, 1],
                "highlights": [0],
                "memos": [
                    {
                        "id": "memo-1",
                        "time": 1.2,
                        "text": "후속 확인",
                        "created_at": "2026-07-18T10:00:00Z",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["title"], "수정된 고객 인터뷰")
        self.assertEqual(payload["segments"][0]["speaker"], "김민수")
        self.assertEqual(payload["segments"][0]["text"], "수정한 문장")
        self.assertEqual(payload["bookmarks"], [1])
        self.assertEqual(payload["highlights"], [0])
        self.assertEqual(payload["memos"][0]["text"], "후속 확인")
        self.assertIsNotNone(payload["transcript_edited_at"])

        from app.core.database import SessionLocal
        from app.models.result import Result

        with SessionLocal() as db:
            stored = db.query(Result).filter(Result.job_id == "editable").one()
            self.assertIn("김민수: 수정한 문장", stored.speaker_transcript)
            self.assertEqual(stored.raw_transcript, "수정한 문장 다음 문장")

    def test_segment_timestamps_cannot_be_changed(self) -> None:
        response = self.client.patch(
            "/api/results/editable",
            json={
                "segments": [
                    {"start": 0.5, "end": 1.0, "speaker": "SPEAKER_00", "text": "원래 문장"},
                    {"start": 1.0, "end": 2.0, "speaker": "SPEAKER_01", "text": "다음 문장"},
                ]
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_segment_text_cannot_be_empty(self) -> None:
        response = self.client.patch(
            "/api/results/editable",
            json={
                "segments": [
                    {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "text": "   "},
                    {"start": 1.0, "end": 2.0, "speaker": "SPEAKER_01", "text": "다음 문장"},
                ]
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_delete_removes_database_records_and_audio_artifacts(self) -> None:
        upload_path = Path(self.temp_dir.name) / "uploads" / "editable.wav"
        processed_path = Path(self.temp_dir.name) / "processed" / "editable.wav"

        response = self.client.delete("/api/jobs/editable")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(upload_path.exists())
        self.assertFalse(processed_path.exists())

        from app.core.database import SessionLocal
        from app.models.job import Job
        from app.models.result import Result

        with SessionLocal() as db:
            self.assertIsNone(db.get(Job, "editable"))
            self.assertIsNone(db.query(Result).filter(Result.job_id == "editable").one_or_none())


if __name__ == "__main__":
    unittest.main()
