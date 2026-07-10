import asyncio
import uuid

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


@router.post("")
async def start_broadcast(
    text: str = Form(...),
    tag_id: str = Form(""),
    image: UploadFile | None = File(None),
):
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

    query = "SELECT user_id, chat_id FROM users"
    params = []
    if tag_id_value is not None:
        query += " WHERE tag_id = $1"
        params.append(tag_id_value)

    async with database.DB_POOL.acquire() as conn:
        rows = await conn.fetch(query, *params)
    recipients = [(row["user_id"], row["chat_id"]) for row in rows]

    broadcast_id = uuid.uuid4().hex
    BROADCASTS[broadcast_id] = {
        "total": len(recipients),
        "sent": 0,
        "blocked": 0,
        "failed": 0,
        "done": False,
    }
    asyncio.create_task(_run_broadcast(broadcast_id, recipients, text, image_bytes, image_filename))

    return {"broadcast_id": broadcast_id, "total": len(recipients)}


@router.get("/{broadcast_id}")
async def get_broadcast_status(broadcast_id: str):
    progress = BROADCASTS.get(broadcast_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")
    return progress


async def _run_broadcast(
    broadcast_id: str,
    recipients: list[tuple[int, int]],
    text: str,
    image_bytes: bytes | None,
    image_filename: str | None,
) -> None:
    progress = BROADCASTS[broadcast_id]
    if not recipients:
        progress["done"] = True
        return

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
        try:
            await send_one(chat_id)
            progress["sent"] += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await send_one(chat_id)
                progress["sent"] += 1
            except TelegramAPIError:
                progress["failed"] += 1
        except TelegramForbiddenError:
            progress["blocked"] += 1
            await mark_blocked(user_id)
        except TelegramAPIError:
            progress["failed"] += 1

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

    progress["done"] = True
