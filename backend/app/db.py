import os
from datetime import datetime
from typing import Generator
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def _build_database_url() -> str:
    """
    Build DB URL from env.

    Expected MySQL env (for docker/external DB):
      - DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

    Also supports:
      - DATABASE_URL (overrides everything)

    Fallback:
      - sqlite:///./auth.db (useful for local development when DB is not configured)
    """

    explicit = (os.getenv("DATABASE_URL") or "").strip()
    if explicit:
        return explicit

    host = (os.getenv("DB_HOST") or "").strip()
    port = (os.getenv("DB_PORT") or "3306").strip()
    name = (os.getenv("DB_NAME") or "").strip()
    user = (os.getenv("DB_USER") or "").strip()
    password = (os.getenv("DB_PASSWORD") or "").strip()

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
    Base.metadata.create_all(bind=engine)


def now_utc() -> datetime:
    return datetime.utcnow()

