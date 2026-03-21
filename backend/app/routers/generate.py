import base64
import json
import os
from typing import Any
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.models.schemas import GenerateResponse
from app.models.user import GenerationHistory, User
from app.db.session import get_db
from app.services.file_parser import ParseFileError, SUPPORTED_FILE_KINDS, extract_extracted_input_from_bytes
from app.services.langfuse_client import LangfuseTrace, build_safe_prompt_preview
from app.services.prompt_builder import build_generation_prompt, build_interface_ts
from app.services.llm_client import LLMClient

router = APIRouter()


def _read_optional_positive_int(name: str) -> int | None:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return None
    val = int(raw)
    if val <= 0:
        return None
    return val


def _read_generation_history_max_input_bytes() -> int:
    """Max raw file size to persist as base64 for /me/generations/.../check-input (default 8 MiB)."""
    raw = (os.getenv("GENERATION_HISTORY_MAX_INPUT_BYTES") or "").strip()
    if not raw:
        return 8 * 1024 * 1024
    try:
        val = int(raw)
        return val if val > 0 else 8 * 1024 * 1024
    except ValueError:
        return 8 * 1024 * 1024


def _coerce_schema_to_dict(schema_obj: Any) -> dict[str, Any] | None:
    if isinstance(schema_obj, dict):
        return schema_obj
    if isinstance(schema_obj, list) and schema_obj and isinstance(schema_obj[0], dict):
        return schema_obj[0]
    return None


def _estimate_tokens_from_text(text: str) -> int:
    # Rough cross-provider estimate: ~4 chars per token for mixed text/code payloads.
    compact = text or ""
    return max(1, (len(compact) + 3) // 4)


def _validate_generated_code_shape(*, code: str, schema_obj: Any, file_kind: str) -> None:
    schema_dict = _coerce_schema_to_dict(schema_obj)
    if schema_dict is None:
        # Invalid schemas are rejected earlier; shape gate should stay non-fatal.
        return

    low = code.lower()
    if "export default function" not in code:
        raise ValueError("generated code missing default export function")

    if file_kind in {"pdf", "docx", "txt", "md", "rtf", "odt", "xml", "epub", "fb2", "doc"}:
        if "parsecsv" in low or "split(';')" in low:
            raise ValueError("document format code incorrectly contains CSV-only parser")

    schema_has_nested = any(isinstance(v, (list, dict)) for v in schema_dict.values())
    if schema_has_nested:
        if 'return string(value ?? "")' in low or "return string(value ?? '')" in low:
            raise ValueError("generated code flattens nested schema values to strings")

    if isinstance(schema_dict.get("input"), list):
        if '"input"' not in code and "input:" not in code:
            raise ValueError("generated code does not preserve required top-level input field")
        if '{"input":""}' in low or '{ "input": "" }' in low:
            raise ValueError("generated code degraded input array into empty string")
        if '{"value":""}' in low or '{ "value": "" }' in low:
            raise ValueError("generated code degraded required input-wrapper into scalar value output")


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    request: Request,
    _user: User = Depends(get_current_user),
    db: AsyncSession | None = Depends(get_db),
    file: UploadFile = File(..., description=f"Uploaded file ({'/'.join(k.upper() for k in SUPPORTED_FILE_KINDS)})"),
    schema: str = Form(..., description="JSON-string schema example for output objects"),
):
    async def _fail_if_disconnected() -> None:
        if await request.is_disconnected():
            raise HTTPException(status_code=499, detail="Client closed request, generation cancelled")

    trace = LangfuseTrace(
        name="generate_request",
        user_id=str(_user.id),
        metadata={"route": "/generate", "filename": file.filename or "unknown"},
    )
    if not file:
        raise HTTPException(status_code=400, detail="file is required")
    if not schema or not schema.strip():
        raise HTTPException(status_code=400, detail="schema is required (JSON string)")

    try:
        schema_obj = json.loads(schema)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid schema JSON: {e}")

    await _fail_if_disconnected()
    with trace.span("read_uploaded_file"):
        contents = await file.read()
    try:
        parse_max_rows = _read_optional_positive_int("PARSE_MAX_ROWS")
        parse_max_text_chars = _read_optional_positive_int("PARSE_MAX_TEXT_CHARS")
        with trace.span(
            "parse_input_file",
            metadata={"content_type": file.content_type, "size_bytes": len(contents)},
        ):
            file_kind, extracted_input_json = extract_extracted_input_from_bytes(
                file.filename,
                file.content_type,
                contents,
                max_rows=parse_max_rows,
                max_text_chars=parse_max_text_chars,
            )
    except ParseFileError as e:
        status = 415 if e.code == "UNSUPPORTED_FILE_TYPE" else 429 if e.code == "GIGACHAT_RATE_LIMIT" else 400
        raise HTTPException(status_code=status, detail=e.as_detail())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse uploaded file: {e}")

    try:
        with trace.span("build_interface_ts"):
            interface_ts = build_interface_ts(schema_obj)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid schema: {e}")

    with trace.span("build_generation_prompt", metadata={"file_kind": file_kind}):
        prompt = build_generation_prompt(
            extracted_input_json, schema_obj, interface_ts=interface_ts, file_kind=file_kind
        )

    await _fail_if_disconnected()
    try:
        client = LLMClient()
        client._active_trace = trace
        with trace.span(
            "generate_typescript",
            input_data=build_safe_prompt_preview(prompt),
            metadata={"provider": client.provider, "file_kind": file_kind},
        ):
            code = client.generate_ts_code(
                prompt=prompt,
                extracted_input_json=extracted_input_json,
                schema_obj=schema_obj,
                interface_ts=interface_ts,
                file_kind=file_kind,
            )
    except Exception as e:
        # Non-hardcoded safety net: deterministic local generator uses current schema + extracted payload.
        try:
            client = LLMClient()
            client._active_trace = trace
            prev_provider = client.provider
            client.provider = "stub"
            try:
                with trace.span("generate_typescript_stub_fallback"):
                    code = client.generate_ts_code(
                        prompt=prompt,
                        extracted_input_json=extracted_input_json,
                        schema_obj=schema_obj,
                        interface_ts=interface_ts,
                        file_kind=file_kind,
                    )
            finally:
                client.provider = prev_provider
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"LLM generation failed: {e}; fallback failed: {e2}")
    usage = getattr(client, "last_usage", {}) or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
    if total_tokens <= 0:
        # Some providers do not return usage in response payload.
        prompt_tokens = _estimate_tokens_from_text(prompt)
        completion_tokens = _estimate_tokens_from_text(code)
        total_tokens = prompt_tokens + completion_tokens

    if not code or not code.strip():
        raise HTTPException(status_code=500, detail="LLM returned empty code")

    try:
        with trace.span("shape_gate_validation"):
            _validate_generated_code_shape(code=code, schema_obj=schema_obj, file_kind=file_kind)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Generated code rejected by shape gate: {e}")

    max_store = _read_generation_history_max_input_bytes()
    input_b64 = base64.b64encode(contents).decode("ascii") if len(contents) <= max_store else None

    await _fail_if_disconnected()
    if db is not None:
        with trace.span("persist_generation_history"):
            db.add(
                GenerationHistory(
                    user_id=_user.id,
                    generated_ts_code=code,
                    schema_text=schema,
                    main_file_name=file.filename or "unknown",
                    input_file_base64=input_b64,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
            )
            await db.commit()

    return GenerateResponse(code=code)

