from __future__ import annotations

import re
import threading
from datetime import datetime
from typing import Dict, List, Optional

from app.models.auth_db import AuthCode, User


class AuthStore:
    """
    Simple in-memory auth storage.
    Notes:
      - No persistence between restarts.
      - Works for MVP/dev to remove DB dependency.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._next_user_id = 1
        self._next_code_id = 1

        self.users_by_id: Dict[int, User] = {}
        self.users_by_email: Dict[str, User] = {}
        self.users_by_login: Dict[str, User] = {}
        self.auth_codes: List[AuthCode] = []

    def _now(self) -> datetime:
        return datetime.utcnow()

    def prune_expired_codes(self) -> None:
        """
        Drop already used or expired codes to keep memory bounded.
        """
        now = self._now()
        with self._lock:
            self.auth_codes = [
                c
                for c in self.auth_codes
                if c.used_at is None and c.expires_at > now
            ]

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        with self._lock:
            return self.users_by_id.get(user_id)

    def _normalize_identifier(self, identifier: str) -> str:
        return (identifier or "").strip()

    def _is_email(self, identifier: str) -> bool:
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", identifier or ""))

    def resolve_user_by_identifier(self, *, identifier: str) -> Optional[User]:
        identifier = self._normalize_identifier(identifier)
        if not identifier:
            return None

        with self._lock:
            if self._is_email(identifier):
                return self.users_by_email.get(identifier)
            return self.users_by_login.get(identifier)

    def register_user(self, *, email: str, login: str, password_hash: str) -> User:
        with self._lock:
            if email in self.users_by_email:
                raise ValueError("Email is already registered")
            if login in self.users_by_login:
                raise ValueError("Login is already taken")

            user = User(
                id=self._next_user_id,
                email=email,
                login=login,
                password_hash=password_hash,
                email_verified=False,
                created_at=self._now(),
            )
            self._next_user_id += 1

            self.users_by_id[user.id] = user
            self.users_by_email[email] = user
            self.users_by_login[login] = user
            return user

    def issue_code(self, *, user_id: int, purpose: str, code_hash: str, expires_at: datetime) -> AuthCode:
        with self._lock:
            entry = AuthCode(
                id=self._next_code_id,
                user_id=user_id,
                purpose=purpose,
                code_hash=code_hash,
                expires_at=expires_at,
                used_at=None,
                created_at=self._now(),
            )
            self._next_code_id += 1
            self.auth_codes.append(entry)
            return entry

    def find_latest_unused_code(self, *, user_id: int, purpose: str) -> Optional[AuthCode]:
        """
        Mimics:
          WHERE user_id=?, purpose=?, expires_at > now, used_at IS NULL
          ORDER BY created_at DESC LIMIT 1
        """
        now = self._now()
        with self._lock:
            # Ensure consistency with prune conditions.
            self.auth_codes = [
                c for c in self.auth_codes if c.used_at is None and c.expires_at > now
            ]
            candidates = [c for c in self.auth_codes if c.user_id == user_id and c.purpose == purpose]
            if not candidates:
                return None
            return max(candidates, key=lambda c: (c.created_at, c.id))


_STORE_SINGLETON = AuthStore()


def get_auth_store() -> AuthStore:
    return _STORE_SINGLETON

