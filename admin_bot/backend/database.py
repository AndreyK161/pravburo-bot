import asyncpg

from config import DATABASE_URL

DB_POOL: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    # command_timeout — если туннель до БД (WireGuard, см. deploy/SPLIT_DEPLOYMENT.md)
    # оборвётся без TCP RST, запрос без таймаута висит вечно и подвешивает API
    # вместо того чтобы упасть с понятной ошибкой.
    global DB_POOL
    DB_POOL = await asyncpg.create_pool(DATABASE_URL, command_timeout=10)


async def close_db_pool() -> None:
    if DB_POOL is not None:
        await DB_POOL.close()
