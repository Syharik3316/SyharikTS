import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import TelegramLinkCode, User
from app.services.auth_tokens import hash_code


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _link_ttl_minutes() -> int:
    return max(1, int(os.getenv("TELEGRAM_LINK_TTL_MINUTES", "10")))


def _max_attempts() -> int:
    return max(1, int(os.getenv("TELEGRAM_LINK_MAX_ATTEMPTS", "5")))


def _random_link_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


async def issue_link_code(db: AsyncSession, user_id: uuid.UUID) -> tuple[str, datetime]:
    code = _random_link_code()
    expires_at = _utcnow() + timedelta(minutes=_link_ttl_minutes())
    await db.execute(
        delete(TelegramLinkCode).where(
            and_(
                TelegramLinkCode.user_id == user_id,
                TelegramLinkCode.consumed_at.is_(None),
            )
        )
    )
    db.add(
        TelegramLinkCode(
            user_id=user_id,
            code_hash=hash_code(code),
            expires_at=expires_at,
            attempts=0,
        )
    )
    await db.commit()
    return code, expires_at


async def consume_link_code(
    db: AsyncSession,
    *,
    code: str,
    chat_id: str,
    username: str | None,
    first_name: str | None,
) -> User | None:
    now = _utcnow()
    row_res = await db.execute(
        select(TelegramLinkCode)
        .where(
            and_(
                TelegramLinkCode.code_hash == hash_code(code.strip().upper()),
                TelegramLinkCode.consumed_at.is_(None),
            )
        )
        .order_by(TelegramLinkCode.created_at.desc())
        .limit(1)
    )
    row = row_res.scalar_one_or_none()
    if row is None:
        return None
    if row.expires_at <= now or row.attempts >= _max_attempts():
        row.attempts = int(row.attempts or 0) + 1
        await db.commit()
        return None

    existing_res = await db.execute(select(User).where(User.telegram_chat_id == chat_id))
    existing = existing_res.scalar_one_or_none()
    if existing is not None and str(existing.id) != str(row.user_id):
        row.attempts = int(row.attempts or 0) + 1
        await db.commit()
        return None

    user_res = await db.execute(select(User).where(User.id == row.user_id))
    user = user_res.scalar_one_or_none()
    if user is None:
        return None
    user.telegram_chat_id = chat_id
    user.telegram_username = (username or "").strip() or None
    user.telegram_first_name = (first_name or "").strip() or None
    user.telegram_linked_at = now
    row.consumed_at = now
    await db.commit()
    return user


async def unlink_telegram(db: AsyncSession, user_id: uuid.UUID) -> None:
    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    if user is None:
        return
    user.telegram_chat_id = None
    user.telegram_username = None
    user.telegram_first_name = None
    user.telegram_linked_at = None
    await db.execute(delete(TelegramLinkCode).where(TelegramLinkCode.user_id == user_id))
    await db.commit()


async def get_user_by_telegram_chat_id(db: AsyncSession, chat_id: str) -> User | None:
    result = await db.execute(select(User).where(User.telegram_chat_id == chat_id))
    return result.scalar_one_or_none()


async def cleanup_expired_codes(db: AsyncSession) -> None:
    await db.execute(
        delete(TelegramLinkCode).where(
            and_(
                TelegramLinkCode.expires_at < func.now(),
                TelegramLinkCode.consumed_at.is_not(None),
            )
        )
    )
    await db.commit()
