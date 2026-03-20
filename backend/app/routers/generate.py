import json
import os
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.schemas import GenerateResponse
from app.services.file_parser import extract_extracted_input
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


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    file: UploadFile = File(..., description="Uploaded file (CSV/XLS/PDF/DOCX/PNG/JPG)"),
    schema: str = Form(..., description="JSON-string schema example for output objects"),
):
    if not file:
        raise HTTPException(status_code=400, detail="file is required")
    if not schema or not schema.strip():
        raise HTTPException(status_code=400, detail="schema is required (JSON string)")

    try:
        schema_obj = json.loads(schema)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid schema JSON: {e}")

    try:
        parse_max_rows = _read_optional_positive_int("PARSE_MAX_ROWS")
        parse_max_text_chars = _read_optional_positive_int("PARSE_MAX_TEXT_CHARS")
        file_kind, extracted_input_json = await extract_extracted_input(
            file,
            max_rows=parse_max_rows,
            max_text_chars=parse_max_text_chars,
        )
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse uploaded file: {e}")

    try:
        interface_ts = build_interface_ts(schema_obj)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid schema: {e}")

    prompt = build_generation_prompt(extracted_input_json, schema_obj, interface_ts=interface_ts)

    try:
        client = LLMClient()
        code = client.generate_ts_code(
            prompt=prompt,
            extracted_input_json=extracted_input_json,
            schema_obj=schema_obj,
            interface_ts=interface_ts,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {e}")

    if not code or not code.strip():
        raise HTTPException(status_code=500, detail="LLM returned empty code")

    # Basic sanity check: the signature must exist.
    if "export default function" not in code:
        raise HTTPException(status_code=500, detail="Generated code missing export default function")

    return GenerateResponse(code=code)

