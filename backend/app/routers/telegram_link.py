import base64
import json
import os
from functools import partial

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, status, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.auth_schemas import (
    BotGenerateResponse,
    BotProfileResponse,
    MessageResponse,
    TelegramConsumeLinkRequest,
    TelegramLinkCodeResponse,
    TelegramStatusResponse,
    TokenUsageItem,
    TokenUsageSummaryResponse,
)
from app.models.user import GenerationHistory, User
from app.routers.generate import (
    _estimate_tokens_from_text,
    _find_cached_generation,
    _read_generation_history_max_input_bytes,
    _validate_generated_code_shape,
)
from app.services.file_parser import ParseFileError, detect_file_kind, extract_extracted_input_from_bytes
from app.services.generation_cache import build_generator_fingerprint, build_input_fingerprint
from app.services.llm_client import LLMClient
from app.services.prompt_builder import build_generation_prompt, build_interface_ts
from app.services.spreadsheet_output_schema import apply_spreadsheet_unmapped_columns_sink
from app.services.telegram_link_service import consume_link_code, get_user_by_telegram_chat_id, issue_link_code, unlink_telegram

router = APIRouter(tags=["telegram"])


def _bot_url() -> str | None:
    username = (os.getenv("TELEGRAM_BOT_USERNAME") or "").strip().lstrip("@")
    if not username:
        return None
    return f"https://t.me/{username}"


def _check_internal_token(internal_token: str | None = Header(default=None, alias="X-Internal-Token")) -> None:
    expected = (os.getenv("TELEGRAM_INTERNAL_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Internal Telegram auth is not configured")
    if not internal_token or internal_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal token")


@router.post("/me/telegram/link-code", response_model=TelegramLinkCodeResponse)
async def create_telegram_link_code(
    db: AsyncSession | None = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")
    code, expires_at = await issue_link_code(db, user.id)
    bot_username = (os.getenv("TELEGRAM_BOT_USERNAME") or "").strip().lstrip("@") or None
    return TelegramLinkCodeResponse(
        link_command=f"/link {code}",
        code_expires_at=expires_at,
        bot_url=_bot_url(),
        bot_username=bot_username,
    )


@router.get("/me/telegram/status", response_model=TelegramStatusResponse)
async def get_telegram_status(
    _db: AsyncSession | None = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return TelegramStatusResponse(
        is_linked=bool(user.telegram_chat_id),
        telegram_chat_id=user.telegram_chat_id,
        telegram_username=user.telegram_username,
        telegram_first_name=user.telegram_first_name,
        telegram_linked_at=user.telegram_linked_at,
    )


@router.post("/me/telegram/unlink", response_model=MessageResponse)
async def unlink_my_telegram(
    db: AsyncSession | None = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")
    await unlink_telegram(db, user.id)
    return MessageResponse(message="Telegram account unlinked")


@router.post("/telegram/consume-link", response_model=TelegramStatusResponse, dependencies=[Depends(_check_internal_token)])
async def consume_telegram_link(
    body: TelegramConsumeLinkRequest,
    db: AsyncSession | None = Depends(get_db),
):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")
    user = await consume_link_code(
        db,
        code=body.code,
        chat_id=body.chat_id,
        username=body.username,
        first_name=body.first_name,
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired link code")
    return TelegramStatusResponse(
        is_linked=True,
        telegram_chat_id=user.telegram_chat_id,
        telegram_username=user.telegram_username,
        telegram_first_name=user.telegram_first_name,
        telegram_linked_at=user.telegram_linked_at,
    )


@router.get("/telegram/me", response_model=BotProfileResponse, dependencies=[Depends(_check_internal_token)])
async def telegram_profile(
    chat_id: str,
    db: AsyncSession | None = Depends(get_db),
):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")
    user = await get_user_by_telegram_chat_id(db, chat_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telegram account is not linked")

    recent_res = await db.execute(
        select(GenerationHistory)
        .where(GenerationHistory.user_id == user.id)
        .order_by(GenerationHistory.created_at.desc())
        .limit(3)
    )
    recent_rows = recent_res.scalars().all()
    recent_generations = [
        {"id": row.id, "created_at": row.created_at, "main_file_name": row.main_file_name}
        for row in recent_rows
    ]

    agg = await db.execute(
        select(
            func.coalesce(func.sum(GenerationHistory.prompt_tokens), 0),
            func.coalesce(func.sum(GenerationHistory.completion_tokens), 0),
            func.coalesce(func.sum(GenerationHistory.total_tokens), 0),
            func.count(GenerationHistory.id),
        ).where(GenerationHistory.user_id == user.id)
    )
    total_prompt, total_completion, total_all, requests_count = agg.one()
    token_rows_res = await db.execute(
        select(GenerationHistory)
        .where(GenerationHistory.user_id == user.id)
        .order_by(GenerationHistory.created_at.desc())
        .limit(3)
    )
    token_rows = token_rows_res.scalars().all()
    token_requests = [
        TokenUsageItem(
            id=row.id,
            created_at=row.created_at,
            main_file_name=row.main_file_name,
            prompt_tokens=int(row.prompt_tokens or 0),
            completion_tokens=int(row.completion_tokens or 0),
            total_tokens=int(row.total_tokens or 0),
        )
        for row in token_rows
    ]
    token_usage = TokenUsageSummaryResponse(
        total_prompt_tokens=int(total_prompt or 0),
        total_completion_tokens=int(total_completion or 0),
        total_tokens=int(total_all or 0),
        requests_count=int(requests_count or 0),
        requests=token_requests,
    )
    return BotProfileResponse(
        id=user.id,
        email=user.email,
        login=user.login,
        telegram_username=user.telegram_username,
        recent_generations=recent_generations,
        token_usage=token_usage,
    )


@router.post("/telegram/generate", response_model=BotGenerateResponse, dependencies=[Depends(_check_internal_token)])
async def telegram_generate(
    chat_id: str = Form(...),
    schema_text: str = Form(..., alias="schema"),
    file: UploadFile = File(...),
    db: AsyncSession | None = Depends(get_db),
):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")
    user = await get_user_by_telegram_chat_id(db, chat_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telegram account is not linked")

    try:
        schema_obj = json.loads(schema_text)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid schema JSON: {e}")
    contents = await file.read()
    try:
        file_kind = detect_file_kind(file.filename, file.content_type)
    except ParseFileError as e:
        status_code = 415 if e.code == "UNSUPPORTED_FILE_TYPE" else 400
        raise HTTPException(status_code=status_code, detail=e.as_detail())

    input_fingerprint = build_input_fingerprint(file_bytes=contents, schema_text=schema_text, file_kind=file_kind)
    client = LLMClient()
    generator_fingerprint = build_generator_fingerprint(provider=client.provider)
    cached = await _find_cached_generation(
        db,
        input_fingerprint=input_fingerprint,
        generator_fingerprint=generator_fingerprint,
    )
    if cached is not None and cached.generated_ts_code and cached.generated_ts_code.strip():
        max_store = _read_generation_history_max_input_bytes()
        input_b64 = base64.b64encode(contents).decode("ascii") if len(contents) <= max_store else None
        db.add(
            GenerationHistory(
                user_id=user.id,
                generated_ts_code=cached.generated_ts_code,
                schema_text=schema_text,
                main_file_name=file.filename or "unknown",
                input_file_base64=input_b64,
                input_fingerprint=input_fingerprint,
                generator_fingerprint=generator_fingerprint,
                cache_hit=True,
                cache_source_generation_id=cached.id,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
            )
        )
        await db.commit()
        return BotGenerateResponse(code=cached.generated_ts_code, cache_hit=True, main_file_name=file.filename or "unknown")

    try:
        file_kind, extracted_input_json = await run_in_threadpool(
            partial(
                extract_extracted_input_from_bytes,
                file.filename,
                file.content_type,
                contents,
            )
        )
        if file_kind in {"csv", "xls", "xlsx"}:
            schema_obj = apply_spreadsheet_unmapped_columns_sink(schema_obj)
        interface_ts = build_interface_ts(schema_obj)
        prompt = build_generation_prompt(
            extracted_input_json,
            schema_obj,
            interface_ts=interface_ts,
            file_kind=file_kind,
        )
        code = await run_in_threadpool(
            client.generate_ts_code,
            prompt=prompt,
            extracted_input_json=extracted_input_json,
            schema_obj=schema_obj,
            interface_ts=interface_ts,
            file_kind=file_kind,
        )
    except ParseFileError as e:
        status_code = 415 if e.code == "UNSUPPORTED_FILE_TYPE" else 429 if e.code == "GIGACHAT_RATE_LIMIT" else 400
        raise HTTPException(status_code=status_code, detail=e.as_detail())
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Generation failed: {e}")

    usage = getattr(client, "last_usage", {}) or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
    if total_tokens <= 0:
        prompt_tokens = _estimate_tokens_from_text(prompt)
        completion_tokens = _estimate_tokens_from_text(code)
        total_tokens = prompt_tokens + completion_tokens

    _validate_generated_code_shape(code=code, schema_obj=schema_obj, file_kind=file_kind)
    max_store = _read_generation_history_max_input_bytes()
    input_b64 = base64.b64encode(contents).decode("ascii") if len(contents) <= max_store else None
    db.add(
        GenerationHistory(
            user_id=user.id,
            generated_ts_code=code,
            schema_text=schema_text,
            main_file_name=file.filename or "unknown",
            input_file_base64=input_b64,
            input_fingerprint=input_fingerprint,
            generator_fingerprint=generator_fingerprint,
            cache_hit=False,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
    )
    await db.commit()
    return BotGenerateResponse(code=code, cache_hit=False, main_file_name=file.filename or "unknown")
