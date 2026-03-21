import unittest

from fastapi.testclient import TestClient

from app.main import create_app


class OpenApiAuthTests(unittest.TestCase):
    def test_openapi_lists_auth_paths(self) -> None:
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json().get("paths") or {}
        self.assertIn("/auth/login", paths)
        self.assertIn("/auth/register", paths)
        self.assertIn("/auth/resend-registration-code", paths)
        self.assertIn("/generate", paths)


if __name__ == "__main__":
    unittest.main()
