import asyncio
import json
import random
from pathlib import Path

from vkbottle import API, Callback, Keyboard
from vkbottle.exception_factory import VKAPIError
from vkbottle.tools import DocMessagesUploader, PhotoMessageUploader

from config import (
    AUTO_NEXT_DELAY_SECONDS,
    CONSULTATION_DONE_BLOCK,
    CONSULTATION_START_BLOCK,
    FILES_DIR,
    IMAGE_EXTENSIONS,
    NEVER_REPLACE_BLOCK,
    SCENARIO_PATH,
    TAG_CONSULTATION_DONE,
    TAG_CONSULTATION_STARTED,
)
from database import set_blocked, set_tag_by_name, update_current_stage
from state import AWAITING_INPUT, LAST_BOT_MESSAGE, USER_ACTIVITY

with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
    SCENARIO = json.load(f)

# VK messages.send кидает эти коды, когда пользователь запретил сообщения
# сообщества (в чёрном списке / не разрешил личные сообщения) — аналог
# TelegramForbiddenError в tg_bot, а не разовый сбой сети.
VK_BLOCKED_ERROR_CODES = {900, 901, 902}

# Файлы сценария (data/files) статичны, поэтому загруженный в VK attachment
# переиспользуем для всех юзеров, а не заливаем заново на каждый показ блока —
# аналог кэша file_id в tg_bot, только на уровне процесса бота.
_FILE_ATTACHMENT_CACHE: dict[Path, str] = {}


# VK ограничивает inline-клавиатуру 6 строками по 5 кнопок (иначе messages.send
# падает с "Keyboard format is invalid: buttons contain too much rows"). В
# сценарии есть блоки с десятком кнопок (по одной в строке, как в tg_bot, это
# не влезло бы) — поэтому при большом числе кнопок пакуем их плотнее по рядам.
MAX_INLINE_ROWS = 6
MAX_BUTTONS_PER_ROW = 5


def _buttons_per_row(count: int) -> int:
    if count <= 0:
        return 1
    per_row = -(-count // MAX_INLINE_ROWS)  # ceil(count / MAX_INLINE_ROWS)
    return min(max(per_row, 1), MAX_BUTTONS_PER_ROW)


def build_keyboard(buttons: list[dict]) -> str | None:
    if not buttons:
        return None

    def button_payload(btn: dict) -> dict:
        # Кнопка может не просто вести в следующий блок, но и запомнить выбор
        # юзера (set_field/set_value) — например "Да/Нет" на вопрос про имущество.
        if "set_field" in btn:
            return {"field": btn["set_field"], "value": btn["set_value"], "block": btn["next"]}
        return {"block": btn["next"]}

    per_row = _buttons_per_row(len(buttons))
    keyboard = Keyboard(inline=True)
    for i, btn in enumerate(buttons):
        if i > 0 and i % per_row == 0:
            keyboard.row()
        # Callback (не Text!) — иначе клик по кнопке придёт как обычное message_new
        # с текстом кнопки, а не как message_event, и message_event_handler его не увидит.
        keyboard.add(Callback(btn["text"], payload=button_payload(btn)))
    return keyboard.get_json()


async def gate_next_block(vk_api: API, user_id: int, next_block_id: str) -> str:
    # Проверка подписки на сообщество сидит в самом первом блоке сценария (обычно
    # "condition"). Если юзер успел отписаться, любой клик по кнопке — хоть
    # новой, хоть старой из истории чата — должен возвращать его на эту
    # проверку заново, а не пускать дальше по next_block_id как ни в чём не бывало.
    start_block = SCENARIO["blocks"][SCENARIO["start"]]
    if start_block["type"] != "condition":
        return next_block_id
    if await is_subscribed(vk_api, start_block, user_id):
        return next_block_id
    return SCENARIO["start"]


async def is_subscribed(vk_api: API, condition_block: dict, user_id: int) -> bool:
    # У condition-блока может не быть vk_channel, если сценарий ещё не размечен
    # под VK (в нём есть только "channel" для tg_bot) — тогда не блокируем
    # прохождение сценария, раз проверять нечего.
    vk_channel = condition_block.get("vk_channel")
    if not vk_channel:
        return True
    try:
        return bool(await vk_api.groups.is_member(group_id=int(vk_channel), user_id=user_id))
    except VKAPIError:
        return False


async def _upload_file_attachment(vk_api: API, peer_id: int, file_path: Path) -> str:
    cached = _FILE_ATTACHMENT_CACHE.get(file_path)
    if cached is not None:
        return cached
    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        attachment = await PhotoMessageUploader(vk_api).upload(str(file_path), peer_id=peer_id)
    else:
        attachment = await DocMessagesUploader(vk_api).upload(str(file_path), peer_id=peer_id)
    _FILE_ATTACHMENT_CACHE[file_path] = attachment
    return attachment


async def send_file(vk_api: API, peer_id: int, file_path: Path) -> None:
    attachment = await _upload_file_attachment(vk_api, peer_id, file_path)
    await vk_api.messages.send(peer_id=peer_id, attachment=attachment, random_id=random.getrandbits(31))


async def send_file_with_caption(
    vk_api: API, peer_id: int, file_path: Path, caption: str, keyboard: str | None
) -> dict:
    attachment = await _upload_file_attachment(vk_api, peer_id, file_path)
    kwargs = {
        "peer_id": peer_id,
        "message": caption,
        "attachment": attachment,
        "random_id": random.getrandbits(31),
    }
    if keyboard is not None:
        kwargs["keyboard"] = keyboard
    message_id = await vk_api.messages.send(**kwargs)
    return {"peer_id": peer_id, "message_id": message_id}


async def show_text(
    vk_api: API, peer_id: int, user_id: int, text: str, keyboard: str | None, should_replace: bool
) -> None:
    prior_message = LAST_BOT_MESSAGE.get(user_id)
    if should_replace and prior_message is not None:
        try:
            await vk_api.messages.edit(
                peer_id=prior_message["peer_id"],
                message_id=prior_message["message_id"],
                message=text,
                keyboard=keyboard,
            )
            return
        except VKAPIError:
            pass  # сообщение могло устареть/удалиться — просто шлём новое ниже

    message_id = await vk_api.messages.send(
        peer_id=peer_id, message=text, keyboard=keyboard, random_id=random.getrandbits(31)
    )
    LAST_BOT_MESSAGE[user_id] = {"peer_id": peer_id, "message_id": message_id}


async def render_block(vk_api: API, peer_id: int, user_id: int, block_id: str, replace: bool = True) -> None:
    # Оборачиваем весь показ блока (включая рекурсивные вызовы условия/паузы/
    # auto_next) — если юзер запретил сообщения от сообщества, любая отправка
    # упадёт с этой ошибкой, и мы просто помечаем его в базе, ничего не роняя дальше.
    try:
        await _render_block(vk_api, peer_id, user_id, block_id, replace)
    except VKAPIError as e:
        if e.code in VK_BLOCKED_ERROR_CODES:
            await set_blocked(user_id, True)
        else:
            raise


async def _render_block(vk_api: API, peer_id: int, user_id: int, block_id: str, replace: bool) -> None:
    block = SCENARIO["blocks"][block_id]

    if block["type"] == "condition":
        subscribed = await is_subscribed(vk_api, block, user_id)
        next_block_id = block["yes"] if subscribed else block["no"]
        await render_block(vk_api, peer_id, user_id, next_block_id, replace=replace)
        return

    if block["type"] == "delay":
        expected_activity = USER_ACTIVITY.get(user_id, 0)

        async def wait_and_continue() -> None:
            await asyncio.sleep(block["seconds"])
            if USER_ACTIVITY.get(user_id, 0) == expected_activity:
                await render_block(vk_api, peer_id, user_id, block["next"])

        asyncio.create_task(wait_and_continue())
        return

    await update_current_stage(user_id, block_id)
    await set_blocked(user_id, False)  # раз дошли досюда — значит, реально отправляем, бот не заблокирован
    if block_id == CONSULTATION_START_BLOCK:
        await set_tag_by_name(user_id, TAG_CONSULTATION_STARTED)
    elif block_id == CONSULTATION_DONE_BLOCK:
        await set_tag_by_name(user_id, TAG_CONSULTATION_DONE)

    keyboard = build_keyboard(block.get("buttons", []))
    prior_message = LAST_BOT_MESSAGE.get(user_id)
    should_replace = replace and prior_message is not None and block_id != NEVER_REPLACE_BLOCK

    if block["type"] == "message":
        await show_text(vk_api, peer_id, user_id, block["text"], keyboard, should_replace)

    elif block["type"] == "input":
        await show_text(vk_api, peer_id, user_id, block["text"], keyboard, should_replace)
        AWAITING_INPUT[user_id] = {
            "save_as": block["save_as"],
            "next": block["next"],
            "validate": block.get("validate"),
        }
        return

    elif block["type"] == "document":
        file_names = block["file"] if isinstance(block["file"], list) else [block["file"]]
        missing = [name for name in file_names if not (FILES_DIR / name).exists()]
        single_image = len(file_names) == 1 and (FILES_DIR / file_names[0]).suffix.lower() in IMAGE_EXTENSIONS
        if missing:
            missing_list = ", ".join(missing)
            text = f"{block['text']}\n\n[файлы ещё не загружены в data/files: {missing_list}]"
            await show_text(vk_api, peer_id, user_id, text, keyboard, should_replace)
        elif single_image:
            sent = await send_file_with_caption(vk_api, peer_id, FILES_DIR / file_names[0], block["text"], keyboard)
            LAST_BOT_MESSAGE[user_id] = sent
        else:
            await show_text(vk_api, peer_id, user_id, block["text"], keyboard, should_replace)
            for name in file_names:
                await send_file(vk_api, peer_id, FILES_DIR / name)

    if block.get("auto_next"):
        # auto_next — следующее звено той же цепочки сообщений, а не переход
        # по кнопке, поэтому шлём новым сообщением, не трогая предыдущее.
        await vk_api.messages.set_activity(peer_id=peer_id, type="typing")
        await asyncio.sleep(AUTO_NEXT_DELAY_SECONDS)
        await render_block(vk_api, peer_id, user_id, block["auto_next"], replace=False)
