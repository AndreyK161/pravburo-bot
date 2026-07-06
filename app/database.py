import asyncpg

from config import DATABASE_URL, USER_FIELD_COLUMNS

# Пул соединений с БД, создаётся при старте в main().
DB_POOL: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    # Схема БД (users, tags, ...) управляется alembic-миграциями из admin/backend,
    # бот только открывает пул и ожидает, что таблицы уже созданы.
    global DB_POOL
    DB_POOL = await asyncpg.create_pool(DATABASE_URL)


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


async def update_current_stage(user_id: int, block_id: str) -> None:
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            "UPDATE users SET current_stage = $1, updated_at = now() WHERE user_id = $2", block_id, user_id
        )


async def set_tag_by_name(user_id: int, tag_name: str) -> None:
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            """
            UPDATE users SET tag_id = (SELECT id FROM tags WHERE name = $1), updated_at = now()
            WHERE user_id = $2
            """,
            tag_name,
            user_id,
        )
