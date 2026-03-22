import hashlib
import json
import os
from typing import Any


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonicalize_schema_text(schema_text: str) -> str:
    schema_obj = json.loads(schema_text)
    return json.dumps(schema_obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_input_fingerprint(*, file_bytes: bytes, schema_text: str, file_kind: str) -> str:
    payload = {
        "file_sha256": _sha256_hex(file_bytes),
        "schema_canonical": canonicalize_schema_text(schema_text),
        "file_kind": (file_kind or "").strip().lower(),
    }
    compact = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_hex(compact.encode("utf-8"))


def get_effective_model_for_provider(provider: str) -> str:
    provider_norm = (provider or "").strip().lower()
    if provider_norm == "openai_compatible":
        return (os.getenv("OPENAI_COMPAT_MODEL") or "").strip()
    if provider_norm == "gigachat":
        return (os.getenv("GIGACHAT_MODEL") or "").strip() or "GigaChat-2-Max"
    if provider_norm == "stub":
        return "stub"
    return ""


def build_generator_fingerprint(*, provider: str, model: str | None = None) -> str:
    prompt_version = (os.getenv("PROMPT_VERSION") or "v3").strip() or "v3"
    effective_model = (model or get_effective_model_for_provider(provider) or "").strip()
    payload: dict[str, Any] = {
        "provider": (provider or "").strip().lower(),
        "model": effective_model,
        "prompt_version": prompt_version,
    }
    compact = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_hex(compact.encode("utf-8"))
