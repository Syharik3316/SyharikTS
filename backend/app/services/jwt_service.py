import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from jose import jwt


def _jwt_secret() -> str:
    secret = (os.getenv("JWT_SECRET") or "").strip()
    if not secret:
        # Avoid breaking local dev/compile when env is missing.
        # In production you MUST set JWT_SECRET.
        secret = "dev-jwt-secret-change-me"
    return secret


def create_access_token(*, user_id: int, email: str, login: str) -> str:
    expires_minutes = int(os.getenv("JWT_ACCESS_EXPIRES_MINUTES") or "60")
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expires_minutes)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "login": login,
        # jose expects numeric timestamps for exp/iat.
        "exp": int(exp.timestamp()),
        "iat": int(now.timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, _jwt_secret(), algorithms=["HS256"])

