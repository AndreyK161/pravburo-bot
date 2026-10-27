from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, ChatMemberUpdated, InlineKeyboardButton, InlineKeyboardMarkup, Message

from antispam import AntiSpamMiddleware
from config import TAG_CONSULTATION_STARTED
from bitrix import send_referral_to_bitrix
from database import (
    cancel_user_steps,
    record_activity,
    save_quiz_answer,
    save_user_field,
    save_user_contact,
    get_consultation_lead,
    save_referral_contact,
    set_tag_by_name_if_untagged,
    upsert_user,
)
from scenario_engine import SCENARIO, gate_next_block, render_block, run_in_background
from state import AWAITING_INPUT, LAST_BOT_MESSAGE, PENDING_DEEPLINK, USER_DATA, touch
from validators import VALIDATORS, parse_contact, parse_referral_contact, validate_name

dp = Dispatcher()

# Диплинки вида t.me/<bot>?start=<блок>_<источник>_<крео>, например
# "kollektory_vk_1" или "mfc_ydxdirect_3" — открывают сразу нужный раздел
# сценария и одновременно размечают источник/креатив для статистики.
# Первая часть должна быть одним из ключей ниже; если это не так (например,
# старые ссылки вида "YDX-DIRECT" без разметки) — строка не парсится и
# целиком идёт в source как раньше, без block/utm_source/utm_campaign.
DEEPLINK_BLOCKS = {
    "consultation": "consultation",
    "chat": "stub_chat",
    "pristavi": "stub_bailiffs",
    "kollektory": "stub_collectors",
    "mfc": "stub_mfc",
    "prikaz": "stub_order",
    "sid": "stub_sid",
    "detskie": "stub_children",
    "otmena": "stub_cancel",
    "checklist": "checklist_menu",
    "banki": "topic_stop_work_for_banks",
}


def parse_deeplink(args: str | None) -> tuple[str | None, str | None, str | None]:
    """Возвращает (block_id, utm_source, utm_campaign) из command.args."""
    if not args:
        return None, None, None
    parts = args.split("_")
    block_id = DEEPLINK_BLOCKS.get(parts[0])
    if block_id is None:
        return None, None, None
    utm_source = parts[1] if len(parts) > 1 and parts[1] else None
    utm_campaign = parts[2] if len(parts) > 2 and parts[2] else None
    return block_id, utm_source, utm_campaign


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


# Срабатывает при добавлении/удалении бота из чата (не зависит от privacy mode,
# в отличие от обычных сообщений) — нужен, чтобы узнать chat_id группы для
# NOTIFY_CHAT_IDS: добавили бота в чат, посмотрели в логах контейнера этот id.
@dp.my_chat_member()
async def on_my_chat_member(update: ChatMemberUpdated) -> None:
    print(
        f"[my_chat_member] chat_id={update.chat.id} title={update.chat.title!r} "
        f"status={update.new_chat_member.status}"
    )


async def mark_active(user_id: int) -> None:
    touch(user_id)
    await record_activity(user_id)


# Command handler
@dp.message(Command("start"))
async def command_start_handler(message: Message, bot: Bot, command: CommandObject) -> None:
    await mark_active(message.from_user.id)
    AWAITING_INPUT.pop(message.from_user.id, None)
    # command.args — это то, что стоит после /start (метка из ссылки вида
    # t.me/tg_bot?start=kollektory_vk_1). При повторных заходах не перезаписывается.
    target_block_id, utm_source, utm_campaign = parse_deeplink(command.args)
    await upsert_user(
        message.from_user.id, message.chat.id, message.from_user.username,
        command.args, utm_source, utm_campaign,
    )
    await set_tag_by_name_if_untagged(message.from_user.id, TAG_CONSULTATION_STARTED)

    PENDING_DEEPLINK.pop(message.from_user.id, None)
    await cancel_user_steps(message.from_user.id)
    if target_block_id:
        start_block_id = await gate_next_block(bot, message.from_user.id, target_block_id)
        if start_block_id != target_block_id:
            # Не подписан — сначала проверка подписки, целевой блок откроется
            # после неё (см. PENDING_DEEPLINK в scenario_engine).
            PENDING_DEEPLINK[message.from_user.id] = target_block_id
    else:
        start_block_id = SCENARIO["start"]

    await render_block(bot, message.chat.id, message.from_user.id, start_block_id, replace=False)


# Кнопка "Даю согласие" в CONSENT_BLOCK — не хранит факт согласия в БД, это
# просто обязательный показ экрана. Ведёт в general_menu, либо, если юзер шёл
# по диплинку на конкретный раздел, туда (см. PENDING_DEEPLINK).
@dp.callback_query(F.data == "consent:accept")
async def consent_accept_handler(callback: CallbackQuery, bot: Bot) -> None:
    await mark_active(callback.from_user.id)
    AWAITING_INPUT.pop(callback.from_user.id, None)
    start_block = SCENARIO["blocks"][SCENARIO["start"]]
    next_block_id = PENDING_DEEPLINK.pop(callback.from_user.id, None) or start_block["yes"]
    await render_block(bot, callback.message.chat.id, callback.from_user.id, next_block_id)
    await safe_answer(callback)


# Callback handler для кнопок сценария (block:<next_block_id>)
@dp.callback_query(F.data.startswith("block:"))
async def scenario_button_handler(callback: CallbackQuery, bot: Bot) -> None:
    await mark_active(callback.from_user.id)
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
    await mark_active(callback.from_user.id)
    AWAITING_INPUT.pop(callback.from_user.id, None)
    payload, next_block_id = callback.data.removeprefix("field:").split(":", 1)
    field, value = payload.split("=", 1)
    await save_user_field(callback.from_user.id, field, value)
    next_block_id = await gate_next_block(bot, callback.from_user.id, next_block_id)
    await render_block(bot, callback.message.chat.id, callback.from_user.id, next_block_id)
    await safe_answer(callback)


# Кнопки квиза: кроме перехода запоминают баллы за ответ
# (quiz:<вопрос>=<баллы>:<next_block_id>). Сумму считаем при подведении итогов.
@dp.callback_query(F.data.startswith("quiz:"))
async def quiz_button_handler(callback: CallbackQuery, bot: Bot) -> None:
    await mark_active(callback.from_user.id)
    AWAITING_INPUT.pop(callback.from_user.id, None)
    payload, next_block_id = callback.data.removeprefix("quiz:").split(":", 1)
    question, score = payload.split("=", 1)
    await save_quiz_answer(callback.from_user.id, question, int(score))
    next_block_id = await gate_next_block(bot, callback.from_user.id, next_block_id)
    await render_block(bot, callback.message.chat.id, callback.from_user.id, next_block_id)
    await safe_answer(callback)


# Защита от произвольного текста: если юзер написал что-то своё вместо
# нажатия кнопки, просто направляем его обратно в главное меню.
# Исключение — если бот ждёт от него конкретный ввод (блок "input").
@dp.message()
async def fallback_text_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    await mark_active(user_id)

    pending = AWAITING_INPUT.get(user_id)
    if pending and pending.get("kind") == "referral":
        contact = parse_referral_contact(message.text)
        if contact is None:
            pending["attempts"] = pending.get("attempts", 0) + 1
            if pending["attempts"] >= 2:
                AWAITING_INPUT.pop(user_id, None)
                await render_block(bot, message.chat.id, user_id, pending["failure"], replace=False)
            else:
                await bot.send_message(
                    message.chat.id,
                    "<b>Кажется, в сообщении нет номера телефона.</b> Пришлите, пожалуйста, имя и номер одним сообщением, например: Сергей, +7 900 123-45-67.",
                    parse_mode="HTML",
                )
            return
        partner = await get_consultation_lead(user_id)
        referral = await save_referral_contact(
            user_id,
            (partner or {}).get("name") or getattr(message.from_user, "full_name", None) or message.from_user.username or str(user_id),
            message.from_user.username,
            contact[0], contact[1], message.chat.id, message.message_id,
        )
        AWAITING_INPUT.pop(user_id, None)
        await render_block(bot, message.chat.id, user_id, pending["next"], replace=False)
        run_in_background(send_referral_to_bitrix(referral))
        return

    if pending and pending.get("collect_name"):
        # Принимаем имя и телефон вместе, либо собираем их в любом порядке.
        # Пока нет обоих значений, не сохраняем неполную заявку и не создаём лид.
        contact = parse_contact(message.text)
        if contact is not None:
            name, phone = contact
            pending["phone"] = phone
            if name:
                pending["name"] = name
        else:
            name = validate_name(message.text)
            if name:
                pending["name"] = name
            else:
                prompt = (
                    "Напишите, пожалуйста, ваше имя без номера. Например: Сергей."
                    if pending.get("phone") else
                    "Не удалось распознать контакт. Пришлите имя и один номер телефона, "
                    "например: Сергей, +7 900 123-45-67."
                )
                await bot.send_message(message.chat.id, prompt)
                return
        if not pending.get("phone"):
            await bot.send_message(
                message.chat.id,
                "Спасибо! Теперь напишите номер телефона. Например: +7 900 123-45-67.",
            )
            return
        if not pending.get("name"):
            await bot.send_message(message.chat.id, "Спасибо! Как к вам обращаться? Напишите ваше имя.")
            return
        await save_user_contact(user_id, pending["name"], pending["phone"])
        USER_DATA.setdefault(user_id, {}).update(name=pending["name"], phone=pending["phone"])
        next_block_id = await gate_next_block(bot, user_id, pending["next"])
        AWAITING_INPUT.pop(user_id, None)
        await render_block(bot, message.chat.id, user_id, next_block_id, replace=False)
        return

    if pending:
        value = message.text
        validator = VALIDATORS.get(pending.get("validate"))
        if validator:
            value = validator(message.text or "")
            if value is None:
                await bot.send_message(
                    message.chat.id,
                    "Не похоже на номер телефона. Введите номер в формате 89005555555",
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
