import random
import time
from contextlib import suppress
from typing import Any, Awaitable, Callable

from config import ANTISPAM_MAX_EVENTS, ANTISPAM_MUTE_SECONDS, ANTISPAM_WINDOW_SECONDS
from state import SPAM_EVENT_TIMES, SPAM_MUTED_UNTIL


def _user_id(event: Any) -> int | None:
    # vkbottle Message (message_new) хранит отправителя в from_id;
    # "сырое" событие message_event (нажатие инлайн-кнопки) — в user_id.
    return getattr(event, "from_id", None) or getattr(event, "user_id", None)


def _peer_id(event: Any) -> int | None:
    return getattr(event, "peer_id", None)


async def _ack_message_event(event: Any, vk_api: Any) -> None:
    # Аналог callback.answer() в tg_bot — снимает "часики" с инлайн-кнопки в VK.
    # У message_new событий event_id нет, поэтому для них это просто no-op.
    event_id = getattr(event, "event_id", None)
    if event_id is None or vk_api is None:
        return
    with suppress(Exception):
        await vk_api.messages.send_message_event_answer(
            event_id=event_id, user_id=_user_id(event), peer_id=_peer_id(event)
        )


class AntiSpamMiddleware:
    """Глушит юзера, если он шлёт сообщения/жмёт кнопки слишком часто.

    Один и тот же экземпляр вызывается и для message_new, и для message_event —
    иначе флуд одним типом событий не учитывал бы флуд другим. В отличие от
    tg_bot (там framework сам инжектит middleware в диспетчер aiogram), здесь
    вызывается явно из handlers.py в начале каждого хендлера: у vkbottle нет
    единой точки подключения middleware сразу на оба типа событий, а логика
    (мьют по user_id, общий счётчик) — та же самая.
    """

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        user_id = _user_id(event)
        if user_id is None:
            return await handler(event, data)

        now = time.monotonic()
        vk_api = data.get("vk_api")

        muted_until = SPAM_MUTED_UNTIL.get(user_id)
        if muted_until is not None:
            if now < muted_until:
                await _ack_message_event(event, vk_api)
                return None
            del SPAM_MUTED_UNTIL[user_id]

        times = SPAM_EVENT_TIMES.setdefault(user_id, [])
        times.append(now)
        cutoff = now - ANTISPAM_WINDOW_SECONDS
        while times and times[0] < cutoff:
            times.pop(0)

        if len(times) > ANTISPAM_MAX_EVENTS:
            SPAM_MUTED_UNTIL[user_id] = now + ANTISPAM_MUTE_SECONDS
            times.clear()
            peer_id = _peer_id(event)
            if vk_api is not None and peer_id is not None:
                await vk_api.messages.send(
                    peer_id=peer_id,
                    message=f"Слишком много сообщений подряд. Подождите {ANTISPAM_MUTE_SECONDS} секунд и напишите снова.",
                    random_id=random.getrandbits(31),
                )
            await _ack_message_event(event, vk_api)
            return None

        return await handler(event, data)
