"""
Распознавание текста с изображений через GigaChat (vision).

Реализует логику из `ai.md`:
1) загрузить файл в `/files` (purpose="general")
2) отправить в `/chat/completions` как `attachments=[file_id]` и включить `function_call="auto"`
"""

from __future__ import annotations

import base64

from app.services.llm_client import LLMClient


def transcribe_image_with_gigachat(contents: bytes, file_kind: str) -> str:
    return LLMClient().transcribe_image_via_gigachat(contents, file_kind)


def transcript_utf8_base64_for_prompt(text: str) -> str:
    """ASCII base64 of UTF-8 transcript for embedding in TS via decodeBase64."""
    return base64.b64encode(text.encode("utf-8")).decode("ascii")
