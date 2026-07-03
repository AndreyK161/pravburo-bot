import asyncio
import json
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import AUTO_NEXT_DELAY_SECONDS, FILES_DIR, IMAGE_EXTENSIONS, NEVER_REPLACE_BLOCK, SCENARIO_PATH
from state import AWAITING_INPUT, LAST_BOT_MESSAGE, USER_ACTIVITY

with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
    SCENARIO = json.load(f)


def build_keyboard(buttons: list[dict]) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn["text"], callback_data=f"block:{btn['next']}")]
        for btn in buttons
    ])


async def is_subscribed(bot: Bot, channel: str, user_id: int) -> bool:
    member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
    return member.status not in ("left", "kicked")


async def send_file(bot: Bot, chat_id: int, file_path: Path) -> None:
    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        await bot.send_photo(chat_id, FSInputFile(file_path))
    else:
        await bot.send_document(chat_id, FSInputFile(file_path))


async def send_file_with_caption(
    bot: Bot, chat_id: int, file_path: Path, caption: str, keyboard: InlineKeyboardMarkup | None
) -> Message:
    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        return await bot.send_photo(chat_id, FSInputFile(file_path), caption=caption, reply_markup=keyboard)
    return await bot.send_document(chat_id, FSInputFile(file_path), caption=caption, reply_markup=keyboard)


async def show_text(
    bot: Bot, chat_id: int, user_id: int, text: str, keyboard: InlineKeyboardMarkup | None, should_replace: bool
) -> None:
    prior_message = LAST_BOT_MESSAGE.get(user_id)
    if should_replace:
        try:
            sent = await prior_message.edit_text(text, reply_markup=keyboard)
            LAST_BOT_MESSAGE[user_id] = sent
            return
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                sent = await bot.send_message(chat_id, text, reply_markup=keyboard)
                LAST_BOT_MESSAGE[user_id] = sent
            return
    sent = await bot.send_message(chat_id, text, reply_markup=keyboard)
    LAST_BOT_MESSAGE[user_id] = sent


async def render_block(bot: Bot, chat_id: int, user_id: int, block_id: str, replace: bool = True) -> None:
    block = SCENARIO["blocks"][block_id]

    if block["type"] == "condition":
        subscribed = await is_subscribed(bot, block["channel"], user_id)
        next_block_id = block["yes"] if subscribed else block["no"]
        await render_block(bot, chat_id, user_id, next_block_id, replace=replace)
        return

    if block["type"] == "delay":
        expected_activity = USER_ACTIVITY.get(user_id, 0)

        async def wait_and_continue() -> None:
            await asyncio.sleep(block["seconds"])
            if USER_ACTIVITY.get(user_id, 0) == expected_activity:
                await render_block(bot, chat_id, user_id, block["next"])

        asyncio.create_task(wait_and_continue())
        return

    keyboard = build_keyboard(block.get("buttons", []))
    prior_message = LAST_BOT_MESSAGE.get(user_id)
    should_replace = replace and prior_message is not None and block_id != NEVER_REPLACE_BLOCK

    if block["type"] == "message":
        await show_text(bot, chat_id, user_id, block["text"], keyboard, should_replace)

    elif block["type"] == "input":
        await show_text(bot, chat_id, user_id, block["text"], keyboard, should_replace)
        AWAITING_INPUT[user_id] = {"save_as": block["save_as"], "next": block["next"]}
        return

    elif block["type"] == "document":
        file_names = block["file"] if isinstance(block["file"], list) else [block["file"]]
        missing = [name for name in file_names if not (FILES_DIR / name).exists()]
        single_image = len(file_names) == 1 and (FILES_DIR / file_names[0]).suffix.lower() in IMAGE_EXTENSIONS
        if missing:
            missing_list = ", ".join(missing)
            text = f"{block['text']}\n\n[файлы ещё не загружены в data/files: {missing_list}]"
            await show_text(bot, chat_id, user_id, text, keyboard, should_replace)
        elif single_image:
            sent = await send_file_with_caption(bot, chat_id, FILES_DIR / file_names[0], block["text"], keyboard)
            LAST_BOT_MESSAGE[user_id] = sent
        else:
            await show_text(bot, chat_id, user_id, block["text"], keyboard, should_replace)
            for name in file_names:
                await send_file(bot, chat_id, FILES_DIR / name)

    if block.get("auto_next"):
        # auto_next — следующее звено той же цепочки сообщений, а не переход
        # по кнопке, поэтому шлём новым сообщением, не трогая предыдущее.
        await bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(AUTO_NEXT_DELAY_SECONDS)
        await render_block(bot, chat_id, user_id, block["auto_next"], replace=False)
