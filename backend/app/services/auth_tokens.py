import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(UTC)


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_refresh_token_raw() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(
    *,
    user: User,
    secret: str,
    algorithm: str = "HS256",
    expire_minutes: int = 15,
) -> str:
    now = _utcnow()
    exp = now + timedelta(minutes=expire_minutes)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "login": user.login,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, secret: str, algorithm: str = "HS256") -> dict:
    return jwt.decode(token, secret, algorithms=[algorithm])


def decode_access_user_id(token: str, secret: str) -> uuid.UUID:
    try:
        data = decode_token(token, secret)
    except JWTError as e:
        raise ValueError("invalid_token") from e
    if data.get("type") != "access":
        raise ValueError("wrong_token_type")
    sub = data.get("sub")
    if not sub:
        raise ValueError("missing_sub")
    return uuid.UUID(str(sub))
