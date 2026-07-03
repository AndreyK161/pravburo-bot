from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import save_user_field, upsert_user
from scenario_engine import SCENARIO, render_block
from state import AWAITING_INPUT, LAST_BOT_MESSAGE, USER_DATA, touch

dp = Dispatcher()


# Command handler
@dp.message(Command("start"))
async def command_start_handler(message: Message, bot: Bot, command: CommandObject) -> None:
    touch(message.from_user.id)
    AWAITING_INPUT.pop(message.from_user.id, None)
    # command.args — это то, что стоит после /start (метка из ссылки вида
    # t.me/bot?start=YDX-DIRECT). При повторных заходах не перезаписывается.
    await upsert_user(message.from_user.id, message.chat.id, message.from_user.username, command.args)
    await render_block(bot, message.chat.id, message.from_user.id, SCENARIO["start"], replace=False)


# Callback handler для кнопок сценария (block:<next_block_id>)
@dp.callback_query(F.data.startswith("block:"))
async def scenario_button_handler(callback: CallbackQuery, bot: Bot) -> None:
    touch(callback.from_user.id)
    AWAITING_INPUT.pop(callback.from_user.id, None)
    next_block_id = callback.data.removeprefix("block:")
    await render_block(bot, callback.message.chat.id, callback.from_user.id, next_block_id)
    await callback.answer()


# Защита от произвольного текста: если юзер написал что-то своё вместо
# нажатия кнопки, просто направляем его обратно в главное меню.
# Исключение — если бот ждёт от него конкретный ввод (блок "input").
@dp.message()
async def fallback_text_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    touch(user_id)

    pending = AWAITING_INPUT.pop(user_id, None)
    if pending:
        USER_DATA.setdefault(user_id, {})[pending["save_as"]] = message.text
        await save_user_field(user_id, pending["save_as"], message.text)
        await render_block(bot, message.chat.id, user_id, pending["next"], replace=False)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="В меню", callback_data="block:general_menu")]
    ])
    sent = await bot.send_message(message.chat.id, "Для возврата в главное меню нажмите ⬇️", reply_markup=keyboard)
    LAST_BOT_MESSAGE[user_id] = sent
