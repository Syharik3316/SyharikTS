import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

from passlib.context import CryptContext

from app.auth_store import AuthStore
from app.models.auth_db import AuthCode, User
from app.services.email_sender import send_auth_code_email
from app.services.jwt_service import create_access_token


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _code_ttl_seconds() -> int:
    return int(os.getenv("AUTH_CODE_TTL_SECONDS") or "600")


def _code_length() -> int:
    # 6-digit by default.
    return int(os.getenv("AUTH_CODE_LENGTH") or "6")


def _generate_numeric_code() -> str:
    length = _code_length()
    # Deterministic length, numeric-only.
    import secrets

    min_n = 10 ** (length - 1)
    max_n = 10**length - 1
    n = secrets.randbelow(max_n - min_n + 1) + min_n
    return str(n)


def _normalize_identifier(identifier: str) -> str:
    return (identifier or "").strip()


def resolve_user_by_identifier(store: AuthStore, *, identifier: str) -> Optional[User]:
    # Keep normalization rules local, but storage lookups are in-memory.
    identifier = _normalize_identifier(identifier)
    if not identifier:
        return None

    # Storage is responsible for mapping email/login to User.
    return store.resolve_user_by_identifier(identifier=identifier)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def hash_code(code: str) -> str:
    # Use same bcrypt hashing; bcrypt includes random salt.
    return pwd_context.hash(code)


def verify_code(code: str, code_hash: str) -> bool:
    return pwd_context.verify(code, code_hash)


def _auth_code_query(
    store: AuthStore,
    *,
    user_id: int,
    purpose: str,
) -> Optional[AuthCode]:
    # In-memory store already applies:
    #   - expires_at > now
    #   - used_at is None
    #   - order by created_at desc limit 1
    return store.find_latest_unused_code(user_id=user_id, purpose=purpose)


def _issue_and_store_code(
    store: AuthStore,
    *,
    user_id: int,
    purpose: str,
) -> Tuple[str, AuthCode]:
    code = _generate_numeric_code()
    expires_at = datetime.utcnow() + timedelta(seconds=_code_ttl_seconds())
    code_hash = hash_code(code)

    entry = store.issue_code(
        user_id=user_id,
        purpose=purpose,
        code_hash=code_hash,
        expires_at=expires_at,
    )
    return code, entry


def _get_user_public(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "login": user.login,
        "emailVerified": bool(user.email_verified),
    }


def register_user(
    store: AuthStore,
    *,
    email: str,
    login: str,
    password: str,
) -> Tuple[str, User]:
    # Uniqueness check (MVP: fast path).
    user = store.register_user(
        email=email,
        login=login,
        password_hash=hash_password(password),
    )
    return "", user


def verify_email_code(
    store: AuthStore,
    *,
    email: str,
    code: str,
) -> User:
    user = resolve_user_by_identifier(store, identifier=email)
    if not user or not user.email:
        raise ValueError("User not found")

    entry = _auth_code_query(store, user_id=user.id, purpose="email_verify")
    if not entry:
        raise ValueError("Invalid or expired code")
    if not verify_code(code, entry.code_hash):
        raise ValueError("Invalid code")

    entry.used_at = datetime.utcnow()
    user.email_verified = True
    return user


def login_user(
    store: AuthStore,
    *,
    identifier: str,
    password: str,
) -> Tuple[str, User]:
    user = resolve_user_by_identifier(store, identifier=identifier)
    if not user:
        raise ValueError("Invalid credentials")
    if not verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials")
    if not user.email_verified:
        raise PermissionError("Email is not verified")

    token = create_access_token(user_id=user.id, email=user.email, login=user.login)
    return token, user


def request_password_reset(
    store: AuthStore,
    *,
    identifier: str,
) -> Tuple[str, User]:
    user = resolve_user_by_identifier(store, identifier=identifier)
    if not user:
        # Do not leak whether account exists.
        raise ValueError("User not found")

    code, _entry = _issue_and_store_code(store, user_id=user.id, purpose="password_reset")
    return code, user


def reset_password(
    store: AuthStore,
    *,
    identifier: str,
    code: str,
    new_password: str,
) -> User:
    user = resolve_user_by_identifier(store, identifier=identifier)
    if not user:
        raise ValueError("User not found")

    entry = _auth_code_query(store, user_id=user.id, purpose="password_reset")
    if not entry:
        raise ValueError("Invalid or expired code")
    if not verify_code(code, entry.code_hash):
        raise ValueError("Invalid code")

    entry.used_at = datetime.utcnow()
    user.password_hash = hash_password(new_password)
    return user


def register_and_send_email_code(
    store: AuthStore,
    *,
    email: str,
    login: str,
    password: str,
) -> User:
    user = store.register_user(
        email=email,
        login=login,
        password_hash=hash_password(password),
    )

    code, _entry = _issue_and_store_code(store, user_id=user.id, purpose="email_verify")
    send_auth_code_email(
        to_email=user.email,
        subject="Код подтверждения email",
        code=code,
    )
    return user


def send_password_reset_email(
    store: AuthStore,
    *,
    identifier: str,
) -> User:
    user = resolve_user_by_identifier(store, identifier=identifier)
    if not user:
        raise ValueError("User not found")

    code, _entry = _issue_and_store_code(store, user_id=user.id, purpose="password_reset")
    send_auth_code_email(
        to_email=user.email,
        subject="Код восстановления пароля",
        code=code,
    )
    return user


def get_public_user(user: User) -> dict:
    return _get_user_public(user)

