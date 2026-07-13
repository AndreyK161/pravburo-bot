import asyncio
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramAPIError
from aiogram.types import BufferedInputFile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

import bot_client
import database
from config import BROADCAST_MAX_CONCURRENCY, BROADCAST_RATE_PER_SECOND

router = APIRouter(prefix="/api/broadcast", tags=["broadcast"])

# Ограничение Telegram на длину подписи к фото — у обычного текстового
# сообщения лимит намного больше (4096), поэтому проверяем только с картинкой.
MAX_PHOTO_CAPTION_LENGTH = 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Рассылка на тысячи получателей идёт минутами — держать HTTP-запрос
# открытым всё это время нельзя (упрётся в таймаут nginx/браузера).
# Поэтому отправка уходит в фоновую задачу, а статус отдаём отдельным
# эндпоинтом по опросу. Хранилище в памяти процесса — процесс один,
# рестарт админки не проблема (просто рассылка начнётся заново вручную).
BROADCASTS: dict[str, dict] = {}


async def _parse_broadcast_input(
    text: str,
    tag_id: str,
    image: UploadFile | None,
) -> tuple[str, int | None, bytes | None, str | None]:
    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Текст сообщения не может быть пустым")

    tag_id_value = int(tag_id) if tag_id else None

    image_bytes: bytes | None = None
    image_filename: str | None = None
    if image is not None and image.filename:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=422, detail="Изображение должно быть JPEG, PNG или WEBP")
        if len(text) > MAX_PHOTO_CAPTION_LENGTH:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"С изображением текст не может быть длиннее {MAX_PHOTO_CAPTION_LENGTH} символов "
                    f"(сейчас {len(text)}) — так ограничивает Telegram"
                ),
            )
        image_bytes = await image.read()
        image_filename = image.filename

    return text, tag_id_value, image_bytes, image_filename


@router.post("")
async def start_broadcast(
    text: str = Form(...),
    tag_id: str = Form(""),
    image: UploadFile | None = File(None),
):
    text, tag_id_value, image_bytes, image_filename = await _parse_broadcast_input(text, tag_id, image)

    recipients = await _fetch_recipients(tag_id_value)

    broadcast_id = uuid.uuid4().hex
    progress = {
        "total": len(recipients),
        "sent": 0,
        "blocked": 0,
        "failed": 0,
        "done": False,
    }
    BROADCASTS[broadcast_id] = progress

    async def on_progress(sent: int, blocked: int, failed: int) -> None:
        progress["sent"] = sent
        progress["blocked"] = blocked
        progress["failed"] = failed

    async def on_done() -> None:
        progress["done"] = True

    asyncio.create_task(_run_broadcast(recipients, text, image_bytes, image_filename, on_progress, on_done))

    return {"broadcast_id": broadcast_id, "total": len(recipients)}


@router.get("/{broadcast_id}")
async def get_broadcast_status(broadcast_id: str):
    progress = BROADCASTS.get(broadcast_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")
    return progress


async def _fetch_recipients(tag_id: int | None) -> list[tuple[int, int]]:
    query = "SELECT user_id, chat_id FROM users"
    params = []
    if tag_id is not None:
        query += " WHERE tag_id = $1"
        params.append(tag_id)

    async with database.DB_POOL.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [(row["user_id"], row["chat_id"]) for row in rows]


async def _run_broadcast(
    recipients: list[tuple[int, int]],
    text: str,
    image_bytes: bytes | None,
    image_filename: str | None,
    on_progress: Callable[[int, int, int], Awaitable[None]],
    on_done: Callable[[], Awaitable[None]],
) -> None:
    if not recipients:
        await on_done()
        return

    sent = 0
    blocked = 0
    failed = 0

    # Загружаем картинку в Telegram один раз, дальше рассылаем по её file_id —
    # иначе на каждого из тысяч получателей заново гнали бы те же байты.
    photo_file_id: str | None = None
    # Ограничивает число одновременных запросов к Telegram — защита от
    # лавины in-flight запросов, если API вдруг начнёт отвечать медленно.
    semaphore = asyncio.Semaphore(BROADCAST_MAX_CONCURRENCY)

    async def mark_blocked(user_id: int) -> None:
        async with database.DB_POOL.acquire() as conn:
            await conn.execute("UPDATE users SET is_blocked = true, updated_at = now() WHERE user_id = $1", user_id)

    async def send_one(chat_id: int) -> None:
        nonlocal photo_file_id
        if image_bytes is not None:
            photo = photo_file_id or BufferedInputFile(image_bytes, filename=image_filename)
            message = await bot_client.bot.send_photo(chat_id, photo=photo, caption=text, parse_mode="HTML")
            if photo_file_id is None:
                photo_file_id = message.photo[-1].file_id
        else:
            await bot_client.bot.send_message(chat_id, text, parse_mode="HTML")

    async def send_with_retry(user_id: int, chat_id: int) -> None:
        nonlocal sent, blocked, failed
        try:
            await send_one(chat_id)
            sent += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await send_one(chat_id)
                sent += 1
            except TelegramAPIError:
                failed += 1
        except TelegramForbiddenError:
            blocked += 1
            await mark_blocked(user_id)
        except TelegramAPIError:
            failed += 1
        await on_progress(sent, blocked, failed)

    async def worker(user_id: int, chat_id: int) -> None:
        async with semaphore:
            await send_with_retry(user_id, chat_id)

    # Первого получателя отправляем отдельно и ждём результата: если есть
    # картинка, нужно успеть получить её file_id до того, как остальные
    # задачи стартуют параллельно — иначе каждая из них попытается заново
    # закачать те же байты вместо переиспользования уже загруженного файла.
    first_user_id, first_chat_id = recipients[0]
    await send_with_retry(first_user_id, first_chat_id)

    # Запускаем отправки с ограничением по темпу (не быстрее лимита Telegram
    # на новые сообщения в секунду), но не ждём ответа перед стартом
    # следующей — задержка сети у разных запросов перекрывается.
    min_interval = 1 / BROADCAST_RATE_PER_SECOND
    tasks = []
    for user_id, chat_id in recipients[1:]:
        tasks.append(asyncio.create_task(worker(user_id, chat_id)))
        await asyncio.sleep(min_interval)

    if tasks:
        await asyncio.gather(*tasks)

    await on_done()


@router.post("/schedule")
async def schedule_broadcast(
    text: str = Form(...),
    tag_id: str = Form(""),
    scheduled_at: str = Form(...),
    image: UploadFile | None = File(None),
):
    text, tag_id_value, image_bytes, image_filename = await _parse_broadcast_input(text, tag_id, image)

    try:
        scheduled_at_value = datetime.fromisoformat(scheduled_at)
    except ValueError:
        raise HTTPException(status_code=422, detail="Некорректный формат даты/времени")
    if scheduled_at_value.tzinfo is None:
        scheduled_at_value = scheduled_at_value.astimezone()
    if scheduled_at_value <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Время рассылки должно быть в будущем")

    broadcast_id = uuid.uuid4()
    async with database.DB_POOL.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO scheduled_broadcasts (id, text, tag_id, image_bytes, image_filename, scheduled_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            broadcast_id, text, tag_id_value, image_bytes, image_filename, scheduled_at_value,
        )

    return {"id": str(broadcast_id)}


@router.get("/scheduled")
async def list_scheduled_broadcasts():
    async with database.DB_POOL.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sb.id, sb.text, sb.tag_id, t.name AS tag_name, sb.scheduled_at, sb.status,
                   sb.total, sb.sent, sb.blocked, sb.failed, sb.created_at
            FROM scheduled_broadcasts sb
            LEFT JOIN tags t ON t.id = sb.tag_id
            WHERE sb.status IN ('pending', 'sending')
               OR sb.created_at > now() - interval '1 day'
            ORDER BY sb.scheduled_at DESC
            """
        )
    return [dict(row) for row in rows]


@router.delete("/scheduled/{broadcast_id}")
async def cancel_scheduled_broadcast(broadcast_id: uuid.UUID):
    async with database.DB_POOL.acquire() as conn:
        result = await conn.execute(
            "UPDATE scheduled_broadcasts SET status = 'cancelled' WHERE id = $1 AND status = 'pending'",
            broadcast_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=409, detail="Рассылку нельзя отменить — она уже отправляется или завершена")
    return {"ok": True}


async def check_due_broadcasts() -> None:
    async with database.DB_POOL.acquire() as conn:
        due = await conn.fetch(
            "SELECT id FROM scheduled_broadcasts WHERE status = 'pending' AND scheduled_at <= now()"
        )
        for row in due:
            broadcast_id = row["id"]
            claimed = await conn.execute(
                "UPDATE scheduled_broadcasts SET status = 'sending' WHERE id = $1 AND status = 'pending'",
                broadcast_id,
            )
            if claimed == "UPDATE 0":
                continue
            asyncio.create_task(_send_scheduled_broadcast(broadcast_id))


async def _send_scheduled_broadcast(broadcast_id: uuid.UUID) -> None:
    async with database.DB_POOL.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT text, tag_id, image_bytes, image_filename FROM scheduled_broadcasts WHERE id = $1",
            broadcast_id,
        )

    recipients = await _fetch_recipients(row["tag_id"])

    async with database.DB_POOL.acquire() as conn:
        await conn.execute(
            "UPDATE scheduled_broadcasts SET total = $1 WHERE id = $2", len(recipients), broadcast_id
        )

    async def on_progress(sent: int, blocked: int, failed: int) -> None:
        async with database.DB_POOL.acquire() as conn:
            await conn.execute(
                "UPDATE scheduled_broadcasts SET sent = $1, blocked = $2, failed = $3 WHERE id = $4",
                sent, blocked, failed, broadcast_id,
            )

    async def on_done() -> None:
        async with database.DB_POOL.acquire() as conn:
            await conn.execute(
                "UPDATE scheduled_broadcasts SET status = 'done' WHERE id = $1", broadcast_id
            )

    await _run_broadcast(recipients, row["text"], row["image_bytes"], row["image_filename"], on_progress, on_done)
