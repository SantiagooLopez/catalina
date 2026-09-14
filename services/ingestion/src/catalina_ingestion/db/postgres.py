from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from catalina_ingestion.core.config import get_settings

_pool: AsyncConnectionPool | None = None


async def open_postgres_pool() -> AsyncConnectionPool:
    global _pool

    if _pool is not None:
        return _pool

    settings = get_settings()

    pool = AsyncConnectionPool(
        conninfo=settings.database_conninfo,
        min_size=settings.database_min_pool_size,
        max_size=settings.database_max_pool_size,
        open=False,
    )

    try:
        await pool.open()
        await pool.wait(timeout=settings.database_connect_timeout)
    except Exception:
        await pool.close()
        raise

    _pool = pool
    return pool


def get_postgres_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("El pool de PostgreSQL no ha sido inicializado")

    return _pool


@asynccontextmanager
async def postgres_connection() -> AsyncIterator[AsyncConnection[Any]]:
    pool = get_postgres_pool()

    async with pool.connection() as connection:
        yield connection


async def close_postgres_pool() -> None:
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None
