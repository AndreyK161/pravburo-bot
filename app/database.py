import asyncpg

from config import DATABASE_URL, USER_FIELD_COLUMNS

# Пул соединений с БД, создаётся при старте в main().
DB_POOL: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    global DB_POOL
    DB_POOL = await asyncpg.create_pool(DATABASE_URL)
    async with DB_POOL.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                username TEXT,
                name TEXT,
                phone TEXT,
                region TEXT,
                source TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)


async def upsert_user(user_id: int, chat_id: int, username: str | None, source: str | None = None) -> None:
    # source не трогаем при повторных заходах — фиксируем метку только с первого /start.
    async with DB_POOL.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, chat_id, username, source)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
            SET chat_id = $2, username = $3, updated_at = now()
        """, user_id, chat_id, username, source)


async def save_user_field(user_id: int, field: str, value: str) -> None:
    if field not in USER_FIELD_COLUMNS:
        return
    async with DB_POOL.acquire() as conn:
        await conn.execute(f"UPDATE users SET {field} = $1, updated_at = now() WHERE user_id = $2", value, user_id)
