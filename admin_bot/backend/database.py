import asyncpg

from config import DATABASE_URL

DB_POOL: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    global DB_POOL
    DB_POOL = await asyncpg.create_pool(DATABASE_URL)


async def close_db_pool() -> None:
    if DB_POOL is not None:
        await DB_POOL.close()
