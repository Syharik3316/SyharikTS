import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

_DB_CONNECT_TIMEOUT = int(os.getenv("DATABASE_CONNECT_TIMEOUT", "10"))


def _format_db_error(exc: BaseException) -> str:
    chunks: list[str] = []
    seen: set[int] = set()
    cur: BaseException | None = exc
    for _ in range(8):
        if cur is None or id(cur) in seen:
            break
        seen.add(id(cur))

        name = type(cur).__name__
        msg = str(cur).strip()
        if msg:
            chunks.append(f"{name}: {msg}")
        else:
            args = getattr(cur, "args", ())
            if args:
                chunks.append(f"{name}: {args!r}")
            else:
                chunks.append(name)

        orig = getattr(cur, "orig", None)
        if isinstance(orig, BaseException) and id(orig) not in seen:
            cur = orig
            continue
        cur = cur.__cause__ or cur.__context__

    out = "; ".join(chunks).strip()
    if not out:
        out = repr(exc).strip()
    if not out:
        out = "Unknown database error"
    return out

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def database_url() -> str | None:
    url = os.getenv("DATABASE_URL", "").strip()
    return url or None


def _ensure_engine():
    global _engine, _session_factory
    url = database_url()
    if not url:
        return None
    if _engine is None:
        _engine = create_async_engine(
            url,
            pool_pre_ping=True,
            connect_args={"timeout": _DB_CONNECT_TIMEOUT},
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


async def check_connection() -> tuple[str, str | None]:
    """Return (state, detail) where state is ok | skipped | error."""
    if not database_url():
        return ("skipped", None)
    try:
        engine = _ensure_engine()
        if engine is None:
            return ("skipped", None)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return ("ok", None)
    except Exception as e:
        detail = _format_db_error(e)
        logger.warning("Database connection check failed: %s: %s", type(e).__name__, detail)
        return ("error", detail)


async def get_db() -> AsyncGenerator[AsyncSession | None, None]:
    if not database_url():
        yield None
        return
    _ensure_engine()
    if _session_factory is None:
        yield None
        return
    async with _session_factory() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
