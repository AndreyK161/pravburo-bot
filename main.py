import asyncio
import json
from os import getenv
from pathlib import Path

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from aiogram.filters import Command

load_dotenv()

TOKEN = getenv("BOT_TOKEN")

dp = Dispatcher()

TEST_DATA_DIR = Path(__file__).parent / "test_data"
FILES_DIR = TEST_DATA_DIR / "files"

with open(TEST_DATA_DIR / "scenario.json", "r", encoding="utf-8") as f:
    SCENARIO = json.load(f)

# Блок, который никогда не редактируется поверх предыдущего сообщения —
# всегда шлётся заново, чтобы пользователь легко находил главное меню в чате.
NEVER_REPLACE_BLOCK = "general_menu"

# Счётчик активности на пользователя: растёт при каждом действии.
# Задержки сверяются с ним, чтобы не сработать, если юзер уже сделал что-то ещё.
USER_ACTIVITY: dict[int, int] = {}

# Последнее сообщение бота на пользователя — то, что заменяем при переходе между блоками.
LAST_BOT_MESSAGE: dict[int, Message] = {}


def touch(user_id: int) -> int:
    USER_ACTIVITY[user_id] = USER_ACTIVITY.get(user_id, 0) + 1
    return USER_ACTIVITY[user_id]


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

    keyboard = build_keyboard(block["buttons"])
    prior_message = LAST_BOT_MESSAGE.get(user_id)
    should_replace = replace and prior_message is not None and block_id != NEVER_REPLACE_BLOCK

    if block["type"] == "message":
        if should_replace:
            try:
                sent = await prior_message.edit_text(block["text"], reply_markup=keyboard)
                LAST_BOT_MESSAGE[user_id] = sent
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    sent = await bot.send_message(chat_id, block["text"], reply_markup=keyboard)
                    LAST_BOT_MESSAGE[user_id] = sent
        else:
            sent = await bot.send_message(chat_id, block["text"], reply_markup=keyboard)
            LAST_BOT_MESSAGE[user_id] = sent

    elif block["type"] == "document":
        if should_replace:
            try:
                await prior_message.delete()
            except TelegramBadRequest:
                pass
        file_path = FILES_DIR / block["file"]
        if file_path.exists():
            sent = await bot.send_document(chat_id, FSInputFile(file_path), caption=block["text"], reply_markup=keyboard)
        else:
            text = f"{block['text']}\n\n[файл {block['file']} ещё не загружен в test_data/files]"
            sent = await bot.send_message(chat_id, text, reply_markup=keyboard)
        LAST_BOT_MESSAGE[user_id] = sent

    if block.get("auto_next"):
        await render_block(bot, chat_id, user_id, block["auto_next"], replace=replace)


# Command handler
@dp.message(Command("start"))
async def command_start_handler(message: Message, bot: Bot) -> None:
    touch(message.from_user.id)
    await render_block(bot, message.chat.id, message.from_user.id, SCENARIO["start"], replace=False)


# Callback handler для кнопок сценария (block:<next_block_id>)
@dp.callback_query(F.data.startswith("block:"))
async def scenario_button_handler(callback: CallbackQuery, bot: Bot) -> None:
    touch(callback.from_user.id)
    next_block_id = callback.data.removeprefix("block:")
    await render_block(bot, callback.message.chat.id, callback.from_user.id, next_block_id)
    await callback.answer()


# Run the bot
async def main() -> None:
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
