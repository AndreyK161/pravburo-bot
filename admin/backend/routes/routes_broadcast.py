import asyncio

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramAPIError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import bot_client
import database
from config import BROADCAST_DELAY_SECONDS

router = APIRouter(prefix="/api/broadcast", tags=["broadcast"])


class BroadcastIn(BaseModel):
    text: str
    tag_id: int | None = None


@router.post("")
async def send_broadcast(body: BroadcastIn):
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Текст сообщения не может быть пустым")

    query = "SELECT chat_id FROM users"
    params = []
    if body.tag_id is not None:
        query += " WHERE tag_id = $1"
        params.append(body.tag_id)

    async with database.DB_POOL.acquire() as conn:
        rows = await conn.fetch(query, *params)
    chat_ids = [row["chat_id"] for row in rows]

    sent = 0
    blocked = 0
    failed = 0

    for chat_id in chat_ids:
        try:
            await bot_client.bot.send_message(chat_id, text)
            sent += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot_client.bot.send_message(chat_id, text)
                sent += 1
            except TelegramAPIError:
                failed += 1
        except TelegramForbiddenError:
            blocked += 1
        except TelegramAPIError:
            failed += 1

        await asyncio.sleep(BROADCAST_DELAY_SECONDS)

    return {"total": len(chat_ids), "sent": sent, "blocked": blocked, "failed": failed}
