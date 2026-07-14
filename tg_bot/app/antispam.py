import time
from contextlib import suppress
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import ANTISPAM_MAX_EVENTS, ANTISPAM_MUTE_SECONDS, ANTISPAM_WINDOW_SECONDS
from state import SPAM_EVENT_TIMES, SPAM_MUTED_UNTIL


def _chat_id(event: TelegramObject) -> int | None:
    if isinstance(event, Message):
        return event.chat.id
    if isinstance(event, CallbackQuery) and event.message:
        return event.message.chat.id
    return None


class AntiSpamMiddleware(BaseMiddleware):
    """Глушит юзера, если он шлёт сообщения/жмёт кнопки слишком часто.

    Один и тот же экземпляр регистрируется и на message, и на callback_query —
    иначе флуд одним типом событий не учитывал бы флуд другим.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        user_id = user.id
        now = time.monotonic()

        muted_until = SPAM_MUTED_UNTIL.get(user_id)
        if muted_until is not None:
            if now < muted_until:
                if isinstance(event, CallbackQuery):
                    with suppress(Exception):
                        await event.answer()
                return
            del SPAM_MUTED_UNTIL[user_id]

        times = SPAM_EVENT_TIMES.setdefault(user_id, [])
        times.append(now)
        cutoff = now - ANTISPAM_WINDOW_SECONDS
        while times and times[0] < cutoff:
            times.pop(0)

        if len(times) > ANTISPAM_MAX_EVENTS:
            SPAM_MUTED_UNTIL[user_id] = now + ANTISPAM_MUTE_SECONDS
            times.clear()
            bot = data.get("tg_bot")
            chat_id = _chat_id(event)
            if bot is not None and chat_id is not None:
                await bot.send_message(
                    chat_id,
                    f"Слишком много сообщений подряд. Подождите {ANTISPAM_MUTE_SECONDS} секунд и напишите снова.",
                )
            if isinstance(event, CallbackQuery):
                with suppress(Exception):
                    await event.answer()
            return

        return await handler(event, data)
