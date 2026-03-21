import json
import os
from typing import Any

import httpx


class BackendClient:
    def __init__(self) -> None:
        self.base_url = (os.getenv("BACKEND_INTERNAL_URL") or "http://127.0.0.1:8000").rstrip("/")
        self.internal_token = (os.getenv("TELEGRAM_INTERNAL_TOKEN") or "").strip()
        self.timeout = float(os.getenv("TELEGRAM_BACKEND_TIMEOUT_SECONDS", "180"))

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": self.internal_token}

    async def consume_link(
        self,
        *,
        code: str,
        chat_id: str,
        username: str | None,
        first_name: str | None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(
                f"{self.base_url}/telegram/consume-link",
                headers=self._headers(),
                json={
                    "code": code.strip().upper(),
                    "chat_id": chat_id,
                    "username": username,
                    "first_name": first_name,
                },
            )
        return self._must_json(res)

    async def get_profile(self, *, chat_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.get(
                f"{self.base_url}/telegram/me",
                headers=self._headers(),
                params={"chat_id": chat_id},
            )
        return self._must_json(res)

    async def generate(self, *, chat_id: str, schema_obj: Any, file_name: str, file_bytes: bytes) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            files = {
                "file": (file_name, file_bytes),
                "chat_id": (None, chat_id),
                "schema": (None, json.dumps(schema_obj, ensure_ascii=False)),
            }
            res = await client.post(
                f"{self.base_url}/telegram/generate",
                headers=self._headers(),
                files=files,
            )
        return self._must_json(res)

    @staticmethod
    def _must_json(response: httpx.Response) -> dict[str, Any]:
        if response.is_success:
            return response.json()
        detail = None
        try:
            payload = response.json()
            detail = payload.get("detail")
        except Exception:
            detail = response.text[:300]
        raise RuntimeError(detail or f"Backend error: {response.status_code}")
