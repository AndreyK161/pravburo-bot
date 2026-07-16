import json
import random

from vkbottle import GroupEventType
from vkbottle.bot import Bot, Message
from vkbottle_types.events.bot_events import MessageEvent

from antispam import AntiSpamMiddleware
from config import TAG_CONSULTATION_STARTED, TOKEN
from database import save_user_field, set_tag_by_name_if_untagged, upsert_user
from scenario_engine import SCENARIO, build_keyboard, gate_next_block, render_block
from state import (
    AWAITING_INPUT,
    LAST_BOT_MESSAGE,
    LAST_PROCESSED_EVENT_ID,
    LAST_PROCESSED_MESSAGE_ID,
    USER_DATA,
    touch,
)
from validators import VALIDATORS

bot = Bot(token=TOKEN)

# Один экземпляр на оба типа событий, чтобы флуд сообщениями и флуд кнопками
# учитывались в общий лимит одного пользователя.
_antispam = AntiSpamMiddleware()


def _parse_start_payload(raw_payload: str | None) -> dict | None:
    # У VK нет слэш-команд как в Telegram — аналог "/start" (в т.ч. с меткой
    # источника) настраивается в сообществе как кнопка "Начать" с payload вида
    # {"command": "start", "source": "..."}, которую VK присылает первым
    # message_new при заходе пользователя в диалог.
    if not raw_payload:
        return None
    try:
        data = json.loads(raw_payload)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("command") == "start" else None


async def _ensure_user(user_id: int, peer_id: int, source: str | None = None) -> None:
    # Вызывается и на "старт" (с меткой источника из payload кнопки "Начать"),
    # и как подстраховка из fallback-обработчика — если сообщество не настроило
    # кнопку "Начать" с нужным payload, юзер всё равно попадёт в базу при первом
    # же сообщении, просто без source. upsert идемпотентен, повторные вызовы безопасны.
    await upsert_user(user_id, peer_id, None, source)
    await set_tag_by_name_if_untagged(user_id, TAG_CONSULTATION_STARTED)


async def _handle_start(message: Message, start_payload: dict) -> None:
    user_id = message.from_id
    touch(user_id)
    AWAITING_INPUT.pop(user_id, None)
    await _ensure_user(user_id, message.peer_id, start_payload.get("source"))
    await render_block(bot.api, message.peer_id, user_id, SCENARIO["start"], replace=False)


async def _handle_fallback_text(message: Message) -> None:
    user_id = message.from_id
    touch(user_id)

    pending = AWAITING_INPUT.get(user_id)
    if pending:
        value = message.text
        validator = VALIDATORS.get(pending.get("validate"))
        if validator:
            value = validator(message.text)
            if value is None:
                await bot.api.messages.send(
                    peer_id=message.peer_id,
                    message="Не похоже на номер телефона. Введите номер в формате +7XXXXXXXXXX или 8XXXXXXXXXX",
                    random_id=random.getrandbits(31),
                )
                return  # ждём ввод ещё раз, AWAITING_INPUT не трогаем

        AWAITING_INPUT.pop(user_id, None)
        USER_DATA.setdefault(user_id, {})[pending["save_as"]] = value
        await save_user_field(user_id, pending["save_as"], value)
        next_block_id = await gate_next_block(bot.api, user_id, pending["next"])
        await render_block(bot.api, message.peer_id, user_id, next_block_id, replace=False)
        return

    # Ведём на SCENARIO["start"] (проверку подписки), а не сразу на general_menu —
    # иначе неподписанный юзер мог зайти в меню в обход проверки, просто написав
    # что угодно в чат вместо нажатия "Проверить подписку".
    await _ensure_user(user_id, message.peer_id)
    keyboard = build_keyboard([{"text": "В меню", "next": SCENARIO["start"]}])
    message_id = await bot.api.messages.send(
        peer_id=message.peer_id,
        message="Для возврата в главное меню нажмите ⬇️",
        keyboard=keyboard,
        random_id=random.getrandbits(31),
    )
    LAST_BOT_MESSAGE[user_id] = {"peer_id": message.peer_id, "message_id": message_id}


def _is_duplicate_message(message: Message) -> bool:
    # VK Bots Long Poll изредка присылает одно и то же message_new повторно
    # (особенность API, усугубляется обрывами polling-запроса) — без дедупа юзер
    # получает один и тот же ответ бота дважды на одно своё сообщение.
    user_id = message.from_id
    seen_id = LAST_PROCESSED_MESSAGE_ID.get(user_id)
    LAST_PROCESSED_MESSAGE_ID[user_id] = message.conversation_message_id
    return seen_id is not None and seen_id == message.conversation_message_id


@bot.on.message()
async def message_new_handler(message: Message) -> None:
    if _is_duplicate_message(message):
        return

    async def dispatch(event: Message, data: dict) -> None:
        start_payload = _parse_start_payload(event.payload)
        if start_payload is not None:
            await _handle_start(event, start_payload)
        elif (event.text or "").strip().lower() == "начать":
            # Кнопка "Начать" в настройках сообщества шлёт payload {"command":"start"},
            # но юзер может и просто написать "начать" руками (например, если кнопка
            # не настроена или он открыл уже существующий диалог) — обрабатываем так же.
            await _handle_start(event, {})
        else:
            await _handle_fallback_text(event)

    await _antispam(dispatch, message, {"vk_api": bot.api})


# Инлайн-кнопки сценария шлют не message_new, а отдельное событие message_event
# (нажатие кнопки в уже отправленном сообщении) — аналог callback_query в Telegram.
@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, dataclass=MessageEvent)
async def message_event_handler(event: MessageEvent) -> None:
    obj = event.object

    user_id = obj.user_id
    seen_event_id = LAST_PROCESSED_EVENT_ID.get(user_id)
    LAST_PROCESSED_EVENT_ID[user_id] = obj.event_id
    if seen_event_id is not None and seen_event_id == obj.event_id:
        return

    async def dispatch(evt, data: dict) -> None:
        user_id = evt.user_id
        touch(user_id)
        AWAITING_INPUT.pop(user_id, None)

        payload = evt.payload or {}
        next_block_id = payload.get("block")

        if next_block_id is not None:
            if "field" in payload:
                await save_user_field(user_id, payload["field"], payload["value"])

            next_block_id = await gate_next_block(bot.api, user_id, next_block_id)
            await render_block(bot.api, evt.peer_id, user_id, next_block_id)

        # Аналог callback.answer() в tg_bot — снимает "часики" с кнопки.
        # Отвечаем в любом случае, даже если payload оказался без "block".
        await bot.api.messages.send_message_event_answer(
            event_id=evt.event_id, user_id=evt.user_id, peer_id=evt.peer_id
        )

    await _antispam(dispatch, obj, {"vk_api": bot.api})
