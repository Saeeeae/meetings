from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


class ApiKeyMiddlewareTests(unittest.TestCase):
    def _make_client(self, **env):
        for mod in [m for m in list(sys.modules) if m.startswith("app.")]:
            del sys.modules[mod]

        self._tmp = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = f"sqlite:///{self._tmp.name}/test.db"
        os.environ["STORAGE_DIR"] = self._tmp.name
        os.environ["MODELS_DIR"] = self._tmp.name
        for key, value in env.items():
            os.environ[key] = value

        from fastapi.testclient import TestClient
        app_main = importlib.import_module("app.main")
        return TestClient(app_main.app)

    def tearDown(self) -> None:
        for var in ("API_KEY", "DATABASE_URL", "STORAGE_DIR", "MODELS_DIR"):
            os.environ.pop(var, None)
        if hasattr(self, "_tmp"):
            self._tmp.cleanup()

    def test_no_auth_required_when_api_key_unset(self) -> None:
        client = self._make_client()
        with client:
            self.assertEqual(client.get("/api/jobs/missing").status_code, 404)

    def test_health_bypasses_api_key(self) -> None:
        client = self._make_client(API_KEY="secret")
        with client:
            self.assertEqual(client.get("/health").status_code, 200)

    def test_protected_endpoint_rejects_without_key(self) -> None:
        client = self._make_client(API_KEY="secret")
        with client:
            self.assertEqual(client.get("/api/jobs/missing").status_code, 401)

    def test_protected_endpoint_accepts_header_key(self) -> None:
        client = self._make_client(API_KEY="secret")
        with client:
            self.assertEqual(
                client.get("/api/jobs/missing", headers={"X-API-Key": "secret"}).status_code,
                404,
            )

    def test_protected_endpoint_accepts_query_string_key(self) -> None:
        client = self._make_client(API_KEY="secret")
        with client:
            self.assertEqual(client.get("/api/jobs/missing?api_key=secret").status_code, 404)


if __name__ == "__main__":
    unittest.main()
