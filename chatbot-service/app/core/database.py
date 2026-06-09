from __future__ import annotations

from pathlib import Path

import asyncpg

from app.core.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for conversation lifecycle storage.")
    _pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def run_migrations() -> None:
    if not settings.chat_auto_migrate or not settings.database_url:
        return
    pool = await get_pool()
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock(hashtext('chatbot_service_migrations'))")
        try:
            for migration in sorted(migrations_dir.glob("*.sql")):
                await conn.execute(migration.read_text())
        finally:
            await conn.execute("SELECT pg_advisory_unlock(hashtext('chatbot_service_migrations'))")
