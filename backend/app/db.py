import os
from datetime import datetime
from typing import Generator
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError

import time


class Base(DeclarativeBase):
    pass


def _build_database_url() -> str:
    """
    Build DB URL from env.

    Expected MySQL env (for docker-compose):
      - DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

    Also supports:
      - DATABASE_URL (overrides everything)

    Fallback:
      - sqlite:///./auth.db (useful for local development when MySQL is not configured)
    """

    explicit = (os.getenv("DATABASE_URL") or "").strip()
    if explicit:
        return explicit

    def _strip_wrapping_quotes(value: str) -> str:
        """
        Env files sometimes wrap values in single/double quotes to avoid escaping issues.
        Docker Compose often passes quotes literally, so we strip only outer quotes.
        """
        v = value.strip()
        if len(v) >= 2 and ((v[0] == "'" and v[-1] == "'") or (v[0] == '"' and v[-1] == '"')):
            return v[1:-1]
        return v

    host = (os.getenv("DB_HOST") or "").strip()
    port = (os.getenv("DB_PORT") or "3306").strip()
    name = (os.getenv("DB_NAME") or "").strip()
    user = (os.getenv("DB_USER") or "").strip()
    password = _strip_wrapping_quotes((os.getenv("DB_PASSWORD") or "").strip())

    if host and name and user and password:
        user_q = quote_plus(user)
        password_q = quote_plus(password)
        return f"mysql+pymysql://{user_q}:{password_q}@{host}:{port}/{name}?charset=utf8mb4"

    return "sqlite:///./auth.db"


DATABASE_URL = _build_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Create tables for MVP (no migrations yet).
    retries = int(os.getenv("DB_CONNECT_RETRIES", "5"))
    delay_s = float(os.getenv("DB_CONNECT_RETRY_DELAY_SECONDS", "2.0"))

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except SQLAlchemyError as e:
            last_err = e
            # Keep log readable in docker output.
            print(
                f"[db] DB init failed (attempt {attempt}/{retries}). "
                f"Will retry in {delay_s}s. Error: {type(e).__name__}: {e}"
            )
            if attempt < retries:
                time.sleep(delay_s)

    # If all attempts failed, surface the last error so container exits clearly.
    if last_err is not None:
        raise last_err


def now_utc() -> datetime:
    return datetime.utcnow()

