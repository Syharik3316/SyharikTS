import os
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

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


def _is_email(identifier: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", identifier or ""))


def resolve_user_by_identifier(db: Session, *, identifier: str) -> Optional[User]:
    identifier = _normalize_identifier(identifier)
    if not identifier:
        return None
    if _is_email(identifier):
        stmt = select(User).where(User.email == identifier)
    else:
        stmt = select(User).where(User.login == identifier)
    return db.execute(stmt).scalars().first()


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
    db: Session,
    *,
    user_id: int,
    purpose: str,
    only_unused: bool = True,
) -> Optional[AuthCode]:
    now = datetime.utcnow()
    stmt = select(AuthCode).where(
        AuthCode.user_id == user_id,
        AuthCode.purpose == purpose,
        AuthCode.expires_at > now,
    )
    if only_unused:
        stmt = stmt.where(AuthCode.used_at.is_(None))
    stmt = stmt.order_by(AuthCode.created_at.desc()).limit(1)
    return db.execute(stmt).scalars().first()


def _issue_and_store_code(
    db: Session,
    *,
    user_id: int,
    purpose: str,
) -> Tuple[str, AuthCode]:
    code = _generate_numeric_code()
    expires_at = datetime.utcnow() + timedelta(seconds=_code_ttl_seconds())
    code_hash = hash_code(code)

    entry = AuthCode(
        user_id=user_id,
        purpose=purpose,
        code_hash=code_hash,
        expires_at=expires_at,
        used_at=None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return code, entry


def _get_user_public(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "login": user.login,
        "emailVerified": bool(user.email_verified),
    }


def register_user(
    db: Session,
    *,
    email: str,
    login: str,
    password: str,
) -> Tuple[str, User]:
    # Uniqueness check (MVP: fast path).
    existing_email = db.execute(select(User).where(User.email == email)).scalars().first()
    if existing_email:
        raise ValueError("Email is already registered")
    existing_login = db.execute(select(User).where(User.login == login)).scalars().first()
    if existing_login:
        raise ValueError("Login is already taken")

    user = User(
        email=email,
        login=login,
        password_hash=hash_password(password),
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return "", user


def verify_email_code(
    db: Session,
    *,
    email: str,
    code: str,
) -> User:
    user = resolve_user_by_identifier(db, identifier=email)
    if not user or not user.email:
        raise ValueError("User not found")

    entry = _auth_code_query(db, user_id=user.id, purpose="email_verify", only_unused=True)
    if not entry:
        raise ValueError("Invalid or expired code")
    if not verify_code(code, entry.code_hash):
        raise ValueError("Invalid code")

    entry.used_at = datetime.utcnow()
    user.email_verified = True
    db.add(entry)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_user(
    db: Session,
    *,
    identifier: str,
    password: str,
) -> Tuple[str, User]:
    user = resolve_user_by_identifier(db, identifier=identifier)
    if not user:
        raise ValueError("Invalid credentials")
    if not verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials")
    if not user.email_verified:
        raise PermissionError("Email is not verified")

    token = create_access_token(user_id=user.id, email=user.email, login=user.login)
    return token, user


def request_password_reset(
    db: Session,
    *,
    identifier: str,
) -> Tuple[str, User]:
    user = resolve_user_by_identifier(db, identifier=identifier)
    if not user:
        # Do not leak whether account exists.
        raise ValueError("User not found")

    code, _entry = _issue_and_store_code(db, user_id=user.id, purpose="password_reset")
    return code, user


def reset_password(
    db: Session,
    *,
    identifier: str,
    code: str,
    new_password: str,
) -> User:
    user = resolve_user_by_identifier(db, identifier=identifier)
    if not user:
        raise ValueError("User not found")

    entry = _auth_code_query(db, user_id=user.id, purpose="password_reset", only_unused=True)
    if not entry:
        raise ValueError("Invalid or expired code")
    if not verify_code(code, entry.code_hash):
        raise ValueError("Invalid code")

    entry.used_at = datetime.utcnow()
    user.password_hash = hash_password(new_password)
    db.add(entry)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def register_and_send_email_code(
    db: Session,
    *,
    email: str,
    login: str,
    password: str,
) -> User:
    user = None
    # Create user.
    _existing_email = db.execute(select(User).where(User.email == email)).scalars().first()
    if _existing_email:
        raise ValueError("Email is already registered")
    _existing_login = db.execute(select(User).where(User.login == login)).scalars().first()
    if _existing_login:
        raise ValueError("Login is already taken")

    user = User(
        email=email,
        login=login,
        password_hash=hash_password(password),
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    code, _entry = _issue_and_store_code(db, user_id=user.id, purpose="email_verify")
    send_auth_code_email(
        to_email=user.email,
        subject="Код подтверждения email",
        code=code,
    )
    return user


def send_password_reset_email(
    db: Session,
    *,
    identifier: str,
) -> User:
    user = resolve_user_by_identifier(db, identifier=identifier)
    if not user:
        raise ValueError("User not found")

    code, _entry = _issue_and_store_code(db, user_id=user.id, purpose="password_reset")
    send_auth_code_email(
        to_email=user.email,
        subject="Код восстановления пароля",
        code=code,
    )
    return user


def get_public_user(user: User) -> dict:
    return _get_user_public(user)

