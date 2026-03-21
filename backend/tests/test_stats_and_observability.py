import os
import unittest
import uuid

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.main import create_app
from app.models.user import User


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeDb:
    def __init__(self):
        self._idx = 0

    async def execute(self, _query):
        self._idx += 1
        if self._idx == 1:
            return _ScalarResult(42)
        if self._idx == 2:
            return _ScalarResult(12)
        if self._idx == 3:
            return _ScalarResult(100.0)
        return _ScalarResult(0)


async def _override_db():
    yield _FakeDb()


async def _override_current_user():
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        login="user",
        password_hash="hash",
        is_email_verified=True,
    )


class StatsAndObservabilityTests(unittest.TestCase):
    def test_stats_requires_auth(self) -> None:
        app = create_app()
        app.dependency_overrides[get_db] = _override_db
        with TestClient(app) as client:
            response = client.get("/stats/generations")
        self.assertEqual(response.status_code, 401)

    def test_stats_returns_total_count(self) -> None:
        app = create_app()
        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = _override_current_user
        with TestClient(app) as client:
            response = client.get("/stats/generations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_generations_all_time"], 42)

    def test_observability_requires_auth(self) -> None:
        app = create_app()
        app.dependency_overrides[get_db] = _override_db
        with TestClient(app) as client:
            response = client.get("/observability/summary")
        self.assertEqual(response.status_code, 401)

    def test_observability_hides_secrets(self) -> None:
        saved = {k: os.environ.get(k) for k in ("LANGFUSE_ENABLED", "LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY")}
        os.environ["LANGFUSE_ENABLED"] = "true"
        os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-test"
        os.environ["LANGFUSE_SECRET_KEY"] = "sk-test"
        try:
            app = create_app()
            app.dependency_overrides[get_current_user] = _override_current_user
            app.dependency_overrides[get_db] = _override_db
            with TestClient(app) as client:
                response = client.get("/observability/summary")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["langfuse_enabled"])
            self.assertNotIn("langfuse_secret_key", body)
            self.assertNotIn("langfuse_public_key", body)
            self.assertEqual(body["generation_cache_total_requests"], 42)
            self.assertEqual(body["generation_cache_hit_count"], 12)
            self.assertAlmostEqual(body["generation_cache_hit_ratio"], 12 / 42)
            self.assertEqual(body["generation_cache_saved_total_tokens_estimate"], 1200)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
