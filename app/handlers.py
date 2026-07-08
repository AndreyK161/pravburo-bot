from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from antispam import AntiSpamMiddleware
from config import TAG_CONSULTATION_STARTED
from database import save_user_field, set_tag_by_name_if_untagged, upsert_user
from scenario_engine import SCENARIO, gate_next_block, render_block
from state import AWAITING_INPUT, LAST_BOT_MESSAGE, USER_DATA, touch
from validators import VALIDATORS

dp = Dispatcher()


async def safe_answer(callback: CallbackQuery) -> None:
    # Если юзер жал кнопку на медленной сети, Telegram может успеть посчитать
    # запрос просроченным ("query is too old") — это не наша ошибка и не повод
    # ронять обработку апдейта, просто нечего ансвертить.
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass


# Один экземпляр на оба типа событий, чтобы флуд сообщениями и флуд кнопками
# учитывались в общий лимит одного пользователя.
_antispam = AntiSpamMiddleware()
dp.message.middleware(_antispam)
dp.callback_query.middleware(_antispam)


# Command handler
@dp.message(Command("start"))
async def command_start_handler(message: Message, bot: Bot, command: CommandObject) -> None:
    touch(message.from_user.id)
    AWAITING_INPUT.pop(message.from_user.id, None)
    # command.args — это то, что стоит после /start (метка из ссылки вида
    # t.me/bot?start=YDX-DIRECT). При повторных заходах не перезаписывается.
    await upsert_user(message.from_user.id, message.chat.id, message.from_user.username, command.args)
    await set_tag_by_name_if_untagged(message.from_user.id, TAG_CONSULTATION_STARTED)
    await render_block(bot, message.chat.id, message.from_user.id, SCENARIO["start"], replace=False)


# Callback handler для кнопок сценария (block:<next_block_id>)
@dp.callback_query(F.data.startswith("block:"))
async def scenario_button_handler(callback: CallbackQuery, bot: Bot) -> None:
    touch(callback.from_user.id)
    AWAITING_INPUT.pop(callback.from_user.id, None)
    next_block_id = callback.data.removeprefix("block:")
    next_block_id = await gate_next_block(bot, callback.from_user.id, next_block_id)
    await render_block(bot, callback.message.chat.id, callback.from_user.id, next_block_id)
    await safe_answer(callback)


# Callback handler для кнопок, которые кроме перехода ещё и запоминают выбор
# юзера (field:<имя_поля>=<значение>:<next_block_id>) — например "Да/Нет"
# на вопрос про залоговое имущество.
@dp.callback_query(F.data.startswith("field:"))
async def scenario_field_button_handler(callback: CallbackQuery, bot: Bot) -> None:
    touch(callback.from_user.id)
    AWAITING_INPUT.pop(callback.from_user.id, None)
    payload, next_block_id = callback.data.removeprefix("field:").split(":", 1)
    field, value = payload.split("=", 1)
    await save_user_field(callback.from_user.id, field, value)
    next_block_id = await gate_next_block(bot, callback.from_user.id, next_block_id)
    await render_block(bot, callback.message.chat.id, callback.from_user.id, next_block_id)
    await safe_answer(callback)


# Защита от произвольного текста: если юзер написал что-то своё вместо
# нажатия кнопки, просто направляем его обратно в главное меню.
# Исключение — если бот ждёт от него конкретный ввод (блок "input").
@dp.message()
async def fallback_text_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    touch(user_id)

    pending = AWAITING_INPUT.get(user_id)
    if pending:
        value = message.text
        validator = VALIDATORS.get(pending.get("validate"))
        if validator:
            value = validator(message.text)
            if value is None:
                await bot.send_message(
                    message.chat.id,
                    "Не похоже на номер телефона. Введите номер в формате +7XXXXXXXXXX или 8XXXXXXXXXX",
                )
                return  # ждём ввод ещё раз, AWAITING_INPUT не трогаем

        AWAITING_INPUT.pop(user_id, None)
        USER_DATA.setdefault(user_id, {})[pending["save_as"]] = value
        await save_user_field(user_id, pending["save_as"], value)
        next_block_id = await gate_next_block(bot, user_id, pending["next"])
        await render_block(bot, message.chat.id, user_id, next_block_id, replace=False)
        return

    # Ведём на SCENARIO["start"] (проверку подписки), а не сразу на general_menu —
    # иначе неподписанный юзер мог зайти в меню в обход проверки, просто написав
    # что угодно в чат вместо нажатия "Проверить подписку".
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="В меню", callback_data=f"block:{SCENARIO['start']}")]
    ])
    sent = await bot.send_message(message.chat.id, "Для возврата в главное меню нажмите ⬇️", reply_markup=keyboard)
    LAST_BOT_MESSAGE[user_id] = sent
