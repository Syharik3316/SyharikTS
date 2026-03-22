import logging
import os
import secrets
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user, jwt_secret
from app.models.auth_schemas import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResendRegistrationCodeRequest,
    ResetConfirmRequest,
    ResetRequestRequest,
    TokenResponse,
    UserPublic,
    VerifyEmailRequest,
)
from app.models.user import EmailVerificationCode, RefreshToken, User
from app.services.auth_tokens import (
    create_access_token,
    hash_code,
    hash_refresh_token,
    new_refresh_token_raw,
)
from app.services.email_service import send_verification_code_email
from app.services.passwords import hash_password, verify_password
from app.services.recaptcha_service import verify_recaptcha_v2

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _access_expire_minutes() -> int:
    return int(os.getenv("JWT_ACCESS_EXPIRE_MINUTES", "15"))


def _refresh_expire_days() -> int:
    return int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7"))


def _code_ttl_minutes() -> int:
    return int(os.getenv("VERIFICATION_CODE_TTL_MINUTES", "15"))


def _resend_registration_cooldown_seconds() -> int:
    return max(1, int(os.getenv("RESEND_VERIFICATION_COOLDOWN_SECONDS", "60")))


def _random_six_digit() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def _require_recaptcha_ok(token: str | None) -> None:
    """Raises HTTPException on failure or if Google siteverify is unreachable (no raw 500)."""
    try:
        ok = await verify_recaptcha_v2(token)
    except httpx.RequestError as e:
        logger.exception("reCAPTCHA siteverify unreachable: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Не удалось проверить reCAPTCHA (сеть). Повторите позже.",
        ) from e
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reCAPTCHA verification failed")


async def _issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    secret = jwt_secret()
    access = create_access_token(
        user=user,
        secret=secret,
        expire_minutes=_access_expire_minutes(),
    )
    raw_refresh = new_refresh_token_raw()
    exp = _utcnow() + timedelta(days=_refresh_expire_days())
    row = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=exp,
        revoked=False,
    )
    db.add(row)
    await db.commit()
    return TokenResponse(access_token=access, refresh_token=raw_refresh)


@router.post("/register", response_model=MessageResponse)
async def register(body: RegisterRequest, db: AsyncSession | None = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")

    await _require_recaptcha_ok(body.recaptcha_token)

    email_l = body.email.lower()
    login_l = body.login.lower()

    try:
        r = await db.execute(select(User).where(func.lower(User.email) == email_l))
        if r.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        r = await db.execute(select(User).where(func.lower(User.login) == login_l))
        if r.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Login already taken")

        user = User(
            email=body.email.strip(),
            login=body.login.strip(),
            password_hash=hash_password(body.password),
            is_email_verified=False,
        )
        db.add(user)
        await db.flush()

        code = _random_six_digit()
        expires = _utcnow() + timedelta(minutes=_code_ttl_minutes())
        await db.execute(
            delete(EmailVerificationCode).where(
                and_(EmailVerificationCode.user_id == user.id, EmailVerificationCode.purpose == "registration")
            )
        )
        db.add(
            EmailVerificationCode(
                user_id=user.id,
                code_hash=hash_code(code),
                purpose="registration",
                expires_at=expires,
            )
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        logger.warning("Register integrity conflict: %s", e)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or login already registered",
        ) from e

    try:
        await send_verification_code_email(user.email, code, "registration")
    except Exception as e:
        logger.exception("Failed to send registration email: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send verification email. Check SMTP settings.",
        ) from e

    return MessageResponse(message="Код подтверждения отправлен на email.")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(body: VerifyEmailRequest, db: AsyncSession | None = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")

    r = await db.execute(select(User).where(func.lower(User.email) == body.email.lower()))
    user = r.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    if user.is_email_verified:
        return MessageResponse(message="Email уже подтверждён.")

    ch = hash_code(body.code)
    now = _utcnow()
    r2 = await db.execute(
        select(EmailVerificationCode).where(
            and_(
                EmailVerificationCode.user_id == user.id,
                EmailVerificationCode.purpose == "registration",
                EmailVerificationCode.code_hash == ch,
                EmailVerificationCode.expires_at > now,
            )
        )
    )
    row = r2.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный или просроченный код")

    user.is_email_verified = True
    await db.execute(
        delete(EmailVerificationCode).where(
            and_(EmailVerificationCode.user_id == user.id, EmailVerificationCode.purpose == "registration")
        )
    )
    await db.commit()
    return MessageResponse(message="Email подтверждён. Можно войти.")


@router.post("/resend-registration-code", response_model=MessageResponse)
async def resend_registration_code(
    body: ResendRegistrationCodeRequest,
    db: AsyncSession | None = Depends(get_db),
):
    """Повторная отправка кода подтверждения регистрации (серверный cooldown)."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")

    generic = MessageResponse(message="Если аккаунт ожидает подтверждения, код отправлен на email.")

    r = await db.execute(select(User).where(func.lower(User.email) == body.email.lower().strip()))
    user = r.scalar_one_or_none()
    if user is None or user.is_email_verified:
        return generic

    now = _utcnow()
    cooldown = _resend_registration_cooldown_seconds()
    r2 = await db.execute(
        select(EmailVerificationCode)
        .where(
            and_(
                EmailVerificationCode.user_id == user.id,
                EmailVerificationCode.purpose == "registration",
            )
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    )
    last = r2.scalar_one_or_none()
    if last is not None:
        created = last.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        next_ok = created + timedelta(seconds=cooldown)
        if next_ok > now:
            wait = max(1, int((next_ok - now).total_seconds()))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": "Слишком частый запрос. Подождите перед повторной отправкой.",
                    "retry_after_seconds": wait,
                },
            )

    code = _random_six_digit()
    expires = now + timedelta(minutes=_code_ttl_minutes())
    await db.execute(
        delete(EmailVerificationCode).where(
            and_(EmailVerificationCode.user_id == user.id, EmailVerificationCode.purpose == "registration")
        )
    )
    db.add(
        EmailVerificationCode(
            user_id=user.id,
            code_hash=hash_code(code),
            purpose="registration",
            expires_at=expires,
        )
    )
    await db.commit()

    try:
        await send_verification_code_email(user.email, code, "registration")
    except Exception as e:
        logger.exception("Failed to resend registration email: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send verification email. Check SMTP settings.",
        ) from e

    return MessageResponse(message="Новый код отправлен на email.")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession | None = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")

    lo = body.login_or_email.strip()
    lo_l = lo.lower()
    r = await db.execute(
        select(User).where(or_(func.lower(User.login) == lo_l, func.lower(User.email) == lo_l))
    )
    user = r.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Complete registration first.",
        )

    return await _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession | None = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")

    th = hash_refresh_token(body.refresh_token.strip())
    now = _utcnow()
    r = await db.execute(
        select(RefreshToken).where(
            and_(
                RefreshToken.token_hash == th,
                RefreshToken.revoked.is_(False),
                RefreshToken.expires_at > now,
            )
        )
    )
    row = r.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    r_user = await db.execute(select(User).where(User.id == row.user_id))
    user = r_user.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    row.revoked = True
    await db.flush()

    secret = jwt_secret()
    access = create_access_token(user=user, secret=secret, expire_minutes=_access_expire_minutes())
    raw_refresh = new_refresh_token_raw()
    exp = _utcnow() + timedelta(days=_refresh_expire_days())
    new_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=exp,
        revoked=False,
    )
    db.add(new_row)
    await db.commit()
    return TokenResponse(access_token=access, refresh_token=raw_refresh)


@router.post("/reset-request", response_model=MessageResponse)
async def reset_request(body: ResetRequestRequest, db: AsyncSession | None = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")

    await _require_recaptcha_ok(body.recaptcha_token)

    r = await db.execute(select(User).where(func.lower(User.email) == body.email.lower()))
    user = r.scalar_one_or_none()

    msg = MessageResponse(message="If an account exists for this email, a reset code was sent.")

    if user is None:
        return msg

    if not user.is_email_verified:
        return msg

    code = _random_six_digit()
    expires = _utcnow() + timedelta(minutes=_code_ttl_minutes())
    await db.execute(
        delete(EmailVerificationCode).where(
            and_(EmailVerificationCode.user_id == user.id, EmailVerificationCode.purpose == "password_reset")
        )
    )
    db.add(
        EmailVerificationCode(
            user_id=user.id,
            code_hash=hash_code(code),
            purpose="password_reset",
            expires_at=expires,
        )
    )
    await db.commit()

    try:
        await send_verification_code_email(user.email, code, "password_reset")
    except Exception as e:
        logger.exception("Failed to send reset email: %s", e)

    return msg


@router.post("/reset-confirm", response_model=MessageResponse)
async def reset_confirm(body: ResetConfirmRequest, db: AsyncSession | None = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not configured")

    r = await db.execute(select(User).where(func.lower(User.email) == body.email.lower()))
    user = r.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code or email")

    ch = hash_code(body.code)
    now = _utcnow()
    r2 = await db.execute(
        select(EmailVerificationCode).where(
            and_(
                EmailVerificationCode.user_id == user.id,
                EmailVerificationCode.purpose == "password_reset",
                EmailVerificationCode.code_hash == ch,
                EmailVerificationCode.expires_at > now,
            )
        )
    )
    row = r2.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    user.password_hash = hash_password(body.new_password)
    await db.execute(
        delete(EmailVerificationCode).where(
            and_(EmailVerificationCode.user_id == user.id, EmailVerificationCode.purpose == "password_reset")
        )
    )
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await db.commit()
    return MessageResponse(message="Password updated. Sign in with your new password.")


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)):
    return UserPublic.model_validate(user)
