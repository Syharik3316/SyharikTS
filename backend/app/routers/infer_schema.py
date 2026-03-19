import json

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import InferSchemaResponse
from app.services.file_parser import extract_extracted_input
from app.services.schema_inferer import infer_schema_from_extracted

router = APIRouter()


@router.post("/infer-schema", response_model=InferSchemaResponse)
async def infer_schema(file: UploadFile = File(...)) -> InferSchemaResponse:
    if not file:
        raise HTTPException(status_code=400, detail="file is required")

    try:
        file_kind, extracted_input_json = await extract_extracted_input(
            file,
            max_rows=5,
            max_text_chars=4000,
        )
        schema_obj = infer_schema_from_extracted(file_kind, extracted_input_json)
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to infer schema: {e}")

    schema_str = json.dumps(schema_obj, ensure_ascii=False)
    return InferSchemaResponse(schema=schema_str)

