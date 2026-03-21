from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.schemas import TotalGenerationsStatsResponse
from app.models.user import GenerationHistory, User

router = APIRouter(tags=["stats"])


@router.get("/stats/generations", response_model=TotalGenerationsStatsResponse)
async def get_total_generations_all_time(
    _user: User = Depends(get_current_user),
    db: AsyncSession | None = Depends(get_db),
):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")
    res = await db.execute(select(func.count(GenerationHistory.id)))
    total = int(res.scalar() or 0)
    return TotalGenerationsStatsResponse(total_generations_all_time=total)
