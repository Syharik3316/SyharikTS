import os
import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

import app.services.image_transcription as image_transcription
from app.dependencies.auth import get_current_user
from app.main import create_app


class GenerateImageFlowTests(unittest.TestCase):
    def test_image_upload_uses_ocr_then_gigachat_codegen(self) -> None:
        app = create_app()

        async def _fake_user():
            return SimpleNamespace(id=1)

        app.dependency_overrides[get_current_user] = _fake_user

        captured = {"prompt": ""}

        def _fake_gigachat_codegen(self, prompt: str, *, file_kind: str, schema_obj):  # noqa: ANN001
            captured["prompt"] = prompt
            return (
                "interface DealData { \"text\": string; }\n"
                "export default function (base64file: string): DealData[] {\n"
                "  if (!String(base64file || '').trim()) return [];\n"
                "  return [{\"text\":\"ok\"} as DealData];\n"
                "}\n"
            )

        with (
            mock.patch.dict(os.environ, {"LLM_PROVIDER": "gigachat"}, clear=False),
            mock.patch.object(image_transcription, "transcribe_image_with_ocr", return_value="Invoice #42\nAmount: 1500"),
            mock.patch("app.services.llm_client.LLMClient._generate_via_gigachat", new=_fake_gigachat_codegen),
        ):
            client = TestClient(app)
            resp = client.post(
                "/generate",
                files={"file": ("scan.png", b"fake-image-bytes", "image/png")},
                data={"schema": '{"text":"string"}'},
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("code", body)
        self.assertIn("Invoice #42", captured["prompt"])


if __name__ == "__main__":
    unittest.main()
