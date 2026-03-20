from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """
    In-memory replacement for the old SQLAlchemy model.
    Stored in runtime memory only (no persistence).
    """

    id: int
    email: str
    login: str
    password_hash: str
    email_verified: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AuthCode:
    """
    In-memory replacement for the old SQLAlchemy model.
    Stored in runtime memory only (no persistence).
    """

    id: int
    user_id: int
    purpose: str  # e.g. email_verify, password_reset
    code_hash: str
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

