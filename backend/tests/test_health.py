import asyncio
import os
import unittest

from fastapi.testclient import TestClient

from app.db.session import dispose_engine
from app.main import create_app


class HealthTests(unittest.TestCase):
    def test_health_database_skipped_without_url(self) -> None:
        saved = os.environ.pop("DATABASE_URL", None)
        try:
            asyncio.run(dispose_engine())
            app = create_app()
            with TestClient(app) as client:
                response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["database"]["state"], "skipped")
            self.assertIsNone(data["database"]["detail"])
        finally:
            asyncio.run(dispose_engine())
            if saved is not None:
                os.environ["DATABASE_URL"] = saved
