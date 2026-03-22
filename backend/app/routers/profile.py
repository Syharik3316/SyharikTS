import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.auth_schemas import (
    GenerationCheckInputResponse,
    GenerationHistoryDetail,
    GenerationHistoryItem,
    ProfileUpdateRequest,
    TokenUsageItem,
    TokenUsageSummaryResponse,
    UserPublic,
)
from app.models.user import GenerationHistory, RefreshToken, User
from app.services.passwords import hash_password, verify_password

router = APIRouter(tags=["profile"])


@router.patch("/profile", response_model=UserPublic)
async def update_profile(
    body: ProfileUpdateRequest,
    db: AsyncSession | None = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")

    if body.login is None and body.new_password is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update")

    try:
        if body.login is not None:
            user.login = body.login.strip()
        if body.new_password is not None:
            user.password_hash = hash_password(body.new_password)
            await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))

        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Login already taken") from e

    return UserPublic.model_validate(user)


@router.get("/me/generations", response_model=list[GenerationHistoryItem])
async def list_generations(
    db: AsyncSession | None = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")

    res = await db.execute(
        select(GenerationHistory)
        .where(GenerationHistory.user_id == user.id)
        .order_by(GenerationHistory.created_at.desc())
    )
    rows = res.scalars().all()
    return [
        GenerationHistoryItem(id=row.id, created_at=row.created_at, main_file_name=row.main_file_name)
        for row in rows
    ]


@router.get("/me/generations/{generation_id}/check-input", response_model=GenerationCheckInputResponse)
async def get_generation_check_input(
    generation_id: uuid.UUID,
    db: AsyncSession | None = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")

    res = await db.execute(
        select(GenerationHistory).where(
            GenerationHistory.user_id == user.id,
            GenerationHistory.id == generation_id,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation not found")

    b64 = row.input_file_base64
    return GenerationCheckInputResponse(input_base64=b64 if isinstance(b64, str) and b64.strip() else None)


@router.get("/me/generations/{generation_id}", response_model=GenerationHistoryDetail)
async def get_generation_detail(
    generation_id: uuid.UUID,
    db: AsyncSession | None = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")

    res = await db.execute(
        select(GenerationHistory).where(
            GenerationHistory.user_id == user.id,
            GenerationHistory.id == generation_id,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation not found")

    return GenerationHistoryDetail(
        id=row.id,
        created_at=row.created_at,
        main_file_name=row.main_file_name,
        generated_ts_code=row.generated_ts_code,
    )


@router.get("/me/token-usage", response_model=TokenUsageSummaryResponse)
async def get_my_token_usage(
    db: AsyncSession | None = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")

    agg = await db.execute(
        select(
            func.coalesce(func.sum(GenerationHistory.prompt_tokens), 0),
            func.coalesce(func.sum(GenerationHistory.completion_tokens), 0),
            func.coalesce(func.sum(GenerationHistory.total_tokens), 0),
            func.count(GenerationHistory.id),
        ).where(GenerationHistory.user_id == user.id)
    )
    total_prompt, total_completion, total_all, requests_count = agg.one()

    rows_res = await db.execute(
        select(GenerationHistory)
        .where(GenerationHistory.user_id == user.id)
        .order_by(GenerationHistory.created_at.desc())
        .limit(50)
    )
    rows = rows_res.scalars().all()
    requests = [
        TokenUsageItem(
            id=row.id,
            created_at=row.created_at,
            main_file_name=row.main_file_name,
            prompt_tokens=int(row.prompt_tokens or 0),
            completion_tokens=int(row.completion_tokens or 0),
            total_tokens=int(row.total_tokens or 0),
        )
        for row in rows
    ]
    return TokenUsageSummaryResponse(
        total_prompt_tokens=int(total_prompt or 0),
        total_completion_tokens=int(total_completion or 0),
        total_tokens=int(total_all or 0),
        requests_count=int(requests_count or 0),
        requests=requests,
    )

