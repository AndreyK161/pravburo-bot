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

# Пауза перед автопереходом (auto_next), чтобы сообщения цепочки не сыпались разом.
AUTO_NEXT_DELAY_SECONDS = 1.5


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

    elif block["type"] == "document":
        file_names = block["file"] if isinstance(block["file"], list) else [block["file"]]
        missing = [name for name in file_names if not (FILES_DIR / name).exists()]
        if missing:
            missing_list = ", ".join(missing)
            text = f"{block['text']}\n\n[файлы ещё не загружены в test_data/files: {missing_list}]"
            await show_text(bot, chat_id, user_id, text, keyboard, should_replace)
        else:
            await show_text(bot, chat_id, user_id, block["text"], keyboard, should_replace)
            for name in file_names:
                await bot.send_document(chat_id, FSInputFile(FILES_DIR / name))

    if block.get("auto_next"):
        # auto_next — следующее звено той же цепочки сообщений, а не переход
        # по кнопке, поэтому шлём новым сообщением, не трогая предыдущее.
        await bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(AUTO_NEXT_DELAY_SECONDS)
        await render_block(bot, chat_id, user_id, block["auto_next"], replace=False)


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


# Защита от произвольного текста: если юзер написал что-то своё вместо
# нажатия кнопки, просто направляем его обратно в главное меню.
@dp.message()
async def fallback_text_handler(message: Message, bot: Bot) -> None:
    touch(message.from_user.id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="В меню", callback_data="block:general_menu")]
    ])
    sent = await bot.send_message(message.chat.id, "Для возврата в главное меню нажмите ⬇️", reply_markup=keyboard)
    LAST_BOT_MESSAGE[message.from_user.id] = sent


# Run the bot
async def main() -> None:
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
