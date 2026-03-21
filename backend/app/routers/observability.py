import os

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.schemas import ObservabilitySummaryResponse
from app.models.user import GenerationHistory, User
from app.services.langfuse_client import get_langfuse_settings

router = APIRouter(tags=["observability"])


@router.get("/observability/summary", response_model=ObservabilitySummaryResponse)
async def get_observability_summary(
    _user: User = Depends(get_current_user),
    db: AsyncSession | None = Depends(get_db),
):
    settings = get_langfuse_settings()
    total_requests = 0
    cache_hit_count = 0
    saved_tokens_estimate = 0
    if db is not None:
        total_res = await db.execute(
            select(func.count(GenerationHistory.id)).where(GenerationHistory.user_id == _user.id)
        )
        total_requests = int(total_res.scalar() or 0)

        hit_res = await db.execute(
            select(func.count(GenerationHistory.id))
            .where(GenerationHistory.user_id == _user.id)
            .where(GenerationHistory.cache_hit.is_(True))
        )
        cache_hit_count = int(hit_res.scalar() or 0)

        avg_miss_tokens_res = await db.execute(
            select(func.avg(GenerationHistory.total_tokens))
            .where(GenerationHistory.user_id == _user.id)
            .where(GenerationHistory.cache_hit.is_(False))
            .where(GenerationHistory.total_tokens.is_not(None))
        )
        avg_miss_tokens = float(avg_miss_tokens_res.scalar() or 0.0)
        saved_tokens_estimate = int(round(cache_hit_count * avg_miss_tokens))

    hit_ratio = (float(cache_hit_count) / float(total_requests)) if total_requests > 0 else 0.0
    return ObservabilitySummaryResponse(
        langfuse_enabled=bool(settings.enabled and settings.public_key and settings.secret_key),
        langfuse_host=settings.host,
        langfuse_env=settings.environment,
        langfuse_release=settings.release,
        llm_provider=(os.getenv("LLM_PROVIDER") or "stub").strip().lower(),
        database_configured=bool((os.getenv("DATABASE_URL") or "").strip()),
        generation_cache_total_requests=total_requests,
        generation_cache_hit_count=cache_hit_count,
        generation_cache_hit_ratio=hit_ratio,
        generation_cache_saved_total_tokens_estimate=max(0, saved_tokens_estimate),
    )
