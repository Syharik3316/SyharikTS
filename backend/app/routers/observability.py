import os

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.models.schemas import ObservabilitySummaryResponse
from app.models.user import User
from app.services.langfuse_client import get_langfuse_settings

router = APIRouter(tags=["observability"])


@router.get("/observability/summary", response_model=ObservabilitySummaryResponse)
async def get_observability_summary(_user: User = Depends(get_current_user)):
    settings = get_langfuse_settings()
    return ObservabilitySummaryResponse(
        langfuse_enabled=bool(settings.enabled and settings.public_key and settings.secret_key),
        langfuse_host=settings.host,
        langfuse_env=settings.environment,
        langfuse_release=settings.release,
        llm_provider=(os.getenv("LLM_PROVIDER") or "stub").strip().lower(),
        database_configured=bool((os.getenv("DATABASE_URL") or "").strip()),
    )
