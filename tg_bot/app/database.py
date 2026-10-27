from datetime import datetime, timedelta, timezone

import asyncpg

from config import DATABASE_URL, USER_FIELD_COLUMNS

# Пул соединений с БД, создаётся при старте в main().
DB_POOL: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    # Схема БД (tg_users, tags, ...) управляется alembic-миграциями из admin_bot/backend,
    # бот только открывает пул и ожидает, что таблицы уже созданы.
    # command_timeout — защита от зависшего запроса при обрыве WireGuard-туннеля
    # до БД (см. deploy/SPLIT_DEPLOYMENT.md): без него запрос виснет навсегда.
    global DB_POOL
    DB_POOL = await asyncpg.create_pool(DATABASE_URL, command_timeout=10)


async def close_db_pool() -> None:
    if DB_POOL is not None:
        await DB_POOL.close()


async def save_referral_contact(
    partner_id: int, partner_name: str, partner_username: str | None,
    contact_name: str, contact_phone: str, chat_id: int, message_id: int,
) -> dict:
    async with DB_POOL.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO referral_contacts
                (partner_telegram_id, partner_name, partner_username,
                 contact_name, contact_phone, chat_id, message_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (chat_id, message_id) DO UPDATE SET message_id = EXCLUDED.message_id
            RETURNING *
            """,
            partner_id, partner_name, partner_username, contact_name, contact_phone, chat_id, message_id,
        )
    return dict(row)


async def claim_referral_for_bitrix(referral_id: int) -> bool:
    async with DB_POOL.acquire() as conn:
        return bool(await conn.fetchval(
            """UPDATE referral_contacts SET bitrix_status = 'sending'
               WHERE id = $1 AND bitrix_status = 'pending' RETURNING id""", referral_id,
        ))


async def finish_referral_bitrix(referral_id: int, status: str, lead_id: int | None = None) -> None:
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            "UPDATE referral_contacts SET bitrix_status = $2, bitrix_lead_id = $3 WHERE id = $1",
            referral_id, status, lead_id,
        )


async def upsert_user(
    user_id: int,
    chat_id: int,
    username: str | None,
    source: str | None = None,
    utm_source: str | None = None,
    utm_campaign: str | None = None,
) -> None:
    # source/utm_* не трогаем при повторных заходах — фиксируем метку только с первого /start.
    async with DB_POOL.acquire() as conn:
        await conn.execute("""
            INSERT INTO tg_users (user_id, chat_id, username, source, utm_source, utm_campaign)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id) DO UPDATE
            SET chat_id = $2, username = $3, updated_at = now()
        """, user_id, chat_id, username, source, utm_source, utm_campaign)


async def save_user_field(user_id: int, field: str, value: str) -> None:
    if field not in USER_FIELD_COLUMNS:
        return
    async with DB_POOL.acquire() as conn:
        await conn.execute(f"UPDATE tg_users SET {field} = $1, updated_at = now() WHERE user_id = $2", value, user_id)


async def save_user_contact(user_id: int, name: str, phone: str) -> None:
    """Имя и номер самого заявителя сохраняются вместе, до создания лида."""
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            "UPDATE tg_users SET name = $2, phone = $3, updated_at = now() WHERE user_id = $1",
            user_id, name, phone,
        )


async def save_quiz_answer(user_id: int, question: str, score: int) -> None:
    # Ответ на вопрос квиза: перезаписывает прошлый ответ на тот же вопрос
    # (при перепрохождении), остальные не трогает.
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            """
            UPDATE tg_users
            SET quiz_answers = quiz_answers || jsonb_build_object($1::text, $2::int), updated_at = now()
            WHERE user_id = $3
            """,
            question, score, user_id,
        )


async def get_quiz_score(user_id: int, prefix: str = "") -> int:
    # Сумма баллов по ответам квиза. prefix отделяет квизы друг от друга: ключи
    # ответов первого квиза начинаются с "q" (q1..q5), второго — с другой буквы.
    async with DB_POOL.acquire() as conn:
        total = await conn.fetchval(
            """
            SELECT COALESCE(SUM(value::int), 0)
            FROM tg_users, jsonb_each_text(quiz_answers)
            WHERE user_id = $1 AND key LIKE $2
            """,
            user_id, prefix + "%",
        )
    return int(total or 0)


async def set_blocked(user_id: int, blocked: bool) -> None:
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            "UPDATE tg_users SET is_blocked = $1, updated_at = now() WHERE user_id = $2", blocked, user_id
        )


async def update_current_stage(user_id: int, block_id: str) -> None:
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            "UPDATE tg_users SET current_stage = $1, updated_at = now() WHERE user_id = $2", block_id, user_id
        )


async def set_tag_by_name(user_id: int, tag_name: str) -> None:
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            """
            UPDATE tg_users SET tag_id = (SELECT id FROM tags WHERE name = $1), updated_at = now()
            WHERE user_id = $2
            """,
            tag_name,
            user_id,
        )


async def get_consultation_lead(user_id: int) -> dict | None:
    async with DB_POOL.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT username, name, phone, region, has_property, source, utm_source, utm_campaign, quiz_answers
            FROM tg_users WHERE user_id = $1
            """,
            user_id,
        )
    return dict(row) if row else None


async def set_tag_by_name_if_untagged(user_id: int, tag_name: str) -> None:
    # Ставим тег только тому, у кого тега ещё нет вообще — чтобы не затирать
    # ни ручной тег админа, ни уже пройденную консультацию.
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            """
            UPDATE tg_users SET tag_id = (SELECT id FROM tags WHERE name = $1), updated_at = now()
            WHERE user_id = $2 AND tag_id IS NULL
            """,
            tag_name,
            user_id,
        )


async def record_activity(user_id: int) -> None:
    # Метка "юзер что-то сделал" — по ней планировщик отменяет напоминания.
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            "UPDATE tg_users SET last_activity_at = $1 WHERE user_id = $2", datetime.now(timezone.utc), user_id
        )


async def get_last_activity(user_id: int) -> datetime | None:
    async with DB_POOL.acquire() as conn:
        return await conn.fetchval("SELECT last_activity_at FROM tg_users WHERE user_id = $1", user_id)


async def schedule_step(
    user_id: int, chat_id: int, next_block_id: str, fire_at: datetime, chain_started_at: datetime, always: bool
) -> None:
    # Если такой же шаг юзеру уже ждёт своего часа (например, дважды нажал кнопку
    # "Нет"), второй не создаём — иначе сообщение придёт дважды.
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO scheduled_steps (user_id, chat_id, next_block_id, fire_at, chain_started_at, always)
            SELECT $1, $2, $3, $4, $5, $6
            WHERE NOT EXISTS (
                SELECT 1 FROM scheduled_steps
                WHERE user_id = $1 AND next_block_id = $3 AND status = 'pending'
            )
            """,
            user_id, chat_id, next_block_id, fire_at, chain_started_at, always,
        )


async def claim_due_steps(limit: int = 50) -> list[dict]:
    # Забираем созревшие шаги одним атомарным запросом (SKIP LOCKED — если
    # запущено несколько копий бота, один шаг достанется только одной).
    async with DB_POOL.acquire() as conn:
        rows = await conn.fetch(
            """
            UPDATE scheduled_steps SET status = 'fired', attempts = attempts + 1
            WHERE id IN (
                SELECT id FROM scheduled_steps
                WHERE status = 'pending' AND fire_at <= $1
                ORDER BY fire_at LIMIT $2 FOR UPDATE SKIP LOCKED
            )
            RETURNING id, user_id, chat_id, next_block_id, chain_started_at, always, attempts
            """,
            datetime.now(timezone.utc), limit,
        )
    return [dict(r) for r in rows]


async def finish_step(step_id: int, status: str) -> None:
    async with DB_POOL.acquire() as conn:
        await conn.execute("UPDATE scheduled_steps SET status = $1 WHERE id = $2", status, step_id)


async def retry_step_later(step_id: int, delay_seconds: int) -> None:
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            "UPDATE scheduled_steps SET status = 'pending', fire_at = $1 WHERE id = $2",
            datetime.now(timezone.utc) + timedelta(seconds=delay_seconds), step_id,
        )


async def defer_step_until(step_id: int, fire_at: datetime) -> None:
    """Возвращает забранный шаг в очередь до разрешённого времени отправки."""
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            "UPDATE scheduled_steps SET status = 'pending', fire_at = $1 WHERE id = $2",
            fire_at,
            step_id,
        )


async def cancel_user_steps(user_id: int) -> None:
    # /start начинает воронку заново — старые отложенные шаги юзера не нужны,
    # иначе одни и те же сообщения придут дважды.
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            "UPDATE scheduled_steps SET status = 'cancelled' WHERE user_id = $1 AND status = 'pending'", user_id
        )
