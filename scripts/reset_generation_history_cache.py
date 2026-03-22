#!/usr/bin/env python3
# Resets generation_history cache columns (migration 005). Reads DATABASE_URL from
# converter-agent/.env or --env. Run: python scripts/reset_generation_history_cache.py [--dry-run]

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def _default_env_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".env"


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f".env не найден: {path}")
    out: dict[str, str] = {}
    text = path.read_text(encoding="utf-8")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, rest = line.partition("=")
        key = key.strip()
        val = rest.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        out[key] = val
    return out


def _to_asyncpg_dsn(database_url: str) -> str:
    u = database_url.strip().strip('"').strip("'")
    prefix = "postgresql+asyncpg://"
    if u.startswith(prefix):
        return "postgresql://" + u[len(prefix) :]
    return u


RESET_SQL = """
UPDATE generation_history
SET
    input_fingerprint = NULL,
    generator_fingerprint = NULL,
    cache_hit = FALSE,
    cache_source_generation_id = NULL
WHERE
    input_fingerprint IS NOT NULL
    OR generator_fingerprint IS NOT NULL
    OR cache_hit IS TRUE
    OR cache_source_generation_id IS NOT NULL
"""


async def _run(*, env_path: Path, dry_run: bool) -> int:
    try:
        import asyncpg
    except ImportError:
        print(
            "Нужен пакет asyncpg. Установите зависимости backend: pip install asyncpg",
            file=sys.stderr,
        )
        return 1

    env = _parse_env_file(env_path)
    raw_url = env.get("DATABASE_URL", "").strip()
    if not raw_url:
        print("В .env нет DATABASE_URL.", file=sys.stderr)
        return 1

    dsn = _to_asyncpg_dsn(raw_url)
    conn = await asyncpg.connect(dsn=dsn)
    try:
        if dry_run:
            n = await conn.fetchval(
                """
                SELECT COUNT(*)::bigint FROM generation_history
                WHERE
                    input_fingerprint IS NOT NULL
                    OR generator_fingerprint IS NOT NULL
                    OR cache_hit IS TRUE
                    OR cache_source_generation_id IS NOT NULL
                """
            )
            print(f"[dry-run] строк с заполненным кэшем: {n}")
            return 0

        status = await conn.execute(RESET_SQL)
        print(status)
        return 0
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Сброс кэш-полей generation_history в PostgreSQL.")
    parser.add_argument(
        "--env",
        type=Path,
        default=_default_env_path(),
        help="Путь к .env (по умолчанию converter-agent/.env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только посчитать строки с ненулевым кэшем, без UPDATE.",
    )
    args = parser.parse_args()
    code = asyncio.run(_run(env_path=args.env.resolve(), dry_run=args.dry_run))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
