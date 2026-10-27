import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import (
    AUTO_NEXT_DELAY_SECONDS,
    CONSENT_BLOCK,
    CONSULTATION_DONE_BLOCK,
    CONSULTATION_START_BLOCK,
    FILES_DIR,
    IMAGE_EXTENSIONS,
    NEVER_REPLACE_BLOCK,
    SCENARIO_PATH,
    TAG_CONSULTATION_DONE,
    TAG_CONSULTATION_STARTED,
)
from database import get_quiz_score, save_quiz_answer, schedule_step, set_blocked, set_tag_by_name, update_current_stage
from bitrix import send_lead_to_bitrix
from notify import notify_consultation_lead
from state import AWAITING_INPUT, LAST_BOT_MESSAGE

logger = logging.getLogger(__name__)

with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
    SCENARIO = json.load(f)


_BACKGROUND_TASKS: set[asyncio.Task] = set()


def run_in_background(coro) -> None:
    # Ссылку на задачу держим в множестве, иначе её может собрать сборщик мусора
    # до завершения; сбой фоновой отправки лида не должен ронять показ блока.
    async def guarded() -> None:
        try:
            await coro
        except Exception:
            logger.exception("Сбой фоновой отправки заявки")

    task = asyncio.create_task(guarded())
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


def build_keyboard(buttons: list[dict], per_row: int = 1) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None

    def callback_data(btn: dict) -> str:
        # Кнопка может не просто вести в следующий блок, но и запомнить выбор
        # юзера (set_field/set_value) — например "Да/Нет" на вопрос про имущество.
        # consent — кнопка согласия в CONSENT_BLOCK, у неё нет фиксированного
        # "next" в JSON: следующий блок решает consent_accept_handler (учитывает
        # PENDING_DEEPLINK), чтобы диплинк не терялся на этом экране.
        if btn.get("consent"):
            return "consent:accept"
        if "quiz_question" in btn:
            return f"quiz:{btn['quiz_question']}={btn['quiz_score']}:{btn['next']}"
        if "set_field" in btn:
            return f"field:{btn['set_field']}={btn['set_value']}:{btn['next']}"
        return f"block:{btn['next']}"

    def make_button(btn: dict) -> InlineKeyboardButton:
        # url — кнопка-ссылка (видео, сайт): открывается в Telegram без callback.
        if btn.get("url"):
            return InlineKeyboardButton(text=btn["text"], url=btn["url"])
        return InlineKeyboardButton(text=btn["text"], callback_data=callback_data(btn))

    # per_row — сколько кнопок в одном ряду (поле блока "buttons_per_row", по умолчанию
    # одна кнопка на ряд). Например, 2 — чтобы "Да"/"Нет" стояли рядом.
    made = [make_button(btn) for btn in buttons]
    return InlineKeyboardMarkup(inline_keyboard=[made[i:i + per_row] for i in range(0, len(made), per_row)])


async def gate_next_block(bot: Bot, user_id: int, next_block_id: str) -> str:
    # Проверка подписки на канал сидит в самом первом блоке сценария (обычно
    # "condition"). Если юзер успел отписаться, любой клик по кнопке — хоть
    # новой, хоть старой из истории чата — должен возвращать его на эту
    # проверку заново, а не пускать дальше по next_block_id как ни в чём не бывало.
    start_block = SCENARIO["blocks"][SCENARIO["start"]]
    if start_block["type"] != "condition":
        return next_block_id
    if await is_subscribed(bot, start_block["channel"], user_id):
        return next_block_id
    return SCENARIO["start"]


async def is_subscribed(bot: Bot, channel: str, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
    except TelegramBadRequest:
        # Telegram кидает ошибку вместо статуса "left", если юзер никогда не
        # состоял в канале (а не просто вышел) — это тоже значит "не подписан".
        return False
    return member.status not in ("left", "kicked")


async def send_file(bot: Bot, chat_id: int, file_path: Path) -> None:
    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        await bot.send_photo(chat_id, FSInputFile(file_path))
    else:
        await bot.send_document(chat_id, FSInputFile(file_path))


async def send_file_with_caption(
    bot: Bot, chat_id: int, file_path: Path, caption: str, keyboard: InlineKeyboardMarkup | None,
    parse_mode: str | None = None,
) -> Message:
    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        return await bot.send_photo(
            chat_id, FSInputFile(file_path), caption=caption, reply_markup=keyboard, parse_mode=parse_mode
        )
    return await bot.send_document(
        chat_id, FSInputFile(file_path), caption=caption, reply_markup=keyboard, parse_mode=parse_mode
    )


async def show_text(
    bot: Bot, chat_id: int, user_id: int, text: str, keyboard: InlineKeyboardMarkup | None, should_replace: bool,
    parse_mode: str | None = None,
) -> None:
    prior_message = LAST_BOT_MESSAGE.get(user_id)
    if should_replace:
        try:
            sent = await prior_message.edit_text(text, reply_markup=keyboard, parse_mode=parse_mode)
            LAST_BOT_MESSAGE[user_id] = sent
            return
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                sent = await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode=parse_mode)
                LAST_BOT_MESSAGE[user_id] = sent
            return
    sent = await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode=parse_mode)
    LAST_BOT_MESSAGE[user_id] = sent


async def render_block(
    bot: Bot, chat_id: int, user_id: int, block_id: str, replace: bool = True, activity: datetime | None = None
) -> None:
    # Оборачиваем весь показ блока (включая рекурсивные вызовы условия/паузы/
    # auto_next) — если юзер заблокировал бота, любая отправка упадёт с этой
    # ошибкой, и мы просто помечаем его в базе, ничего не роняя дальше.
    try:
        await _render_block(bot, chat_id, user_id, block_id, replace, activity)
    except TelegramForbiddenError:
        await set_blocked(user_id, True)


async def _render_block(
    bot: Bot, chat_id: int, user_id: int, block_id: str, replace: bool, activity: datetime | None
) -> None:
    block = SCENARIO["blocks"][block_id]
    # Момент старта цепочки. Планировщик отменяет напоминание, если юзер был
    # активен позже этого момента: между блоком и паузой есть задержка auto_next,
    # и нажатие в это окно иначе не учитывалось бы.
    activity = datetime.now(timezone.utc) if activity is None else activity

    if block["type"] == "condition":
        subscribed = await is_subscribed(bot, block["channel"], user_id)
        # CONSENT_BLOCK — экран согласия на обработку перс. данных, показывается
        # каждый раз перед general_menu/целью диплинка (нигде не запоминаем,
        # согласился юзер или нет — это просто обязательный показ, не учёт).
        next_block_id = CONSENT_BLOCK if subscribed else block["no"]
        await render_block(bot, chat_id, user_id, next_block_id, replace=replace, activity=activity)
        return

    if block["type"] == "quiz_result":
        # Развилка по сумме баллов квиза: берём первый диапазон, в который
        # попадает сумма (score <= max), иначе — default.
        score = await get_quiz_score(user_id, block.get("prefix", ""))
        next_block_id = next((r["next"] for r in block["ranges"] if score <= r["max"]), block["default"])
        await render_block(bot, chat_id, user_id, next_block_id, replace=replace, activity=activity)
        return

    if block["type"] == "delay":
        # Пауза хранится в БД (scheduled_steps), а не в памяти — переживает
        # перезапуск бота. Отправку делает планировщик (scheduler.py): обычная
        # пауза отменяется, если после старта цепочки юзер что-то делал;
        # always — срабатывает в любом случае.
        fire_at = datetime.now(timezone.utc) + timedelta(seconds=block["seconds"])
        await schedule_step(user_id, chat_id, block["next"], fire_at, activity, bool(block.get("always")))
        return

    await update_current_stage(user_id, block_id)
    if block.get("lead_service") in ("mfc", "consultation"):
        # Служебная метка услуги переживает перезапуск; не является ответом квиза.
        await save_quiz_answer(user_id, "service_mfc", int(block["lead_service"] == "mfc"))
    await set_blocked(user_id, False)  # раз дошли досюда — значит, реально отправляем, бот не заблокирован
    if block_id == CONSULTATION_START_BLOCK:
        await set_tag_by_name(user_id, TAG_CONSULTATION_STARTED)

    keyboard = build_keyboard(block.get("buttons", []), block.get("buttons_per_row", 1))
    # html: true — в тексте блока можно использовать <a href="...">ссылки</a>, <b> и т.п.
    parse_mode = "HTML" if block.get("html") else None
    prior_message = LAST_BOT_MESSAGE.get(user_id)
    should_replace = replace and prior_message is not None and block_id != NEVER_REPLACE_BLOCK

    if block["type"] == "message":
        await show_text(bot, chat_id, user_id, block["text"], keyboard, should_replace, parse_mode)

    elif block["type"] == "referral_input":
        await show_text(bot, chat_id, user_id, block["text"], keyboard, should_replace, parse_mode)
        AWAITING_INPUT[user_id] = {
            "kind": "referral",
            "next": block["next"],
            "failure": block["failure"],
            "attempts": 0,
        }
        return

    elif block["type"] == "input":
        await show_text(bot, chat_id, user_id, block["text"], keyboard, should_replace, parse_mode)
        AWAITING_INPUT[user_id] = {
            "save_as": block["save_as"],
            "next": block["next"],
            "validate": block.get("validate"),
        }
        if block.get("collect_name"):
            AWAITING_INPUT[user_id]["collect_name"] = True
        return

    elif block["type"] == "video":
        # Обычная видеоинструкция, не Telegram-кружок.
        if (FILES_DIR / block["file"]).exists():
            sent = await bot.send_video(chat_id, FSInputFile(FILES_DIR / block["file"]))
            LAST_BOT_MESSAGE[user_id] = sent
        else:
            await show_text(bot, chat_id, user_id, f"[видео ещё не загружено в data/files: {block['file']}]", None, False)

    elif block["type"] == "video_note":
        # Кружок. Кнопок у него быть не может (ограничение Telegram), поэтому
        # текст с кнопками идёт следующим блоком через auto_next.
        if (FILES_DIR / block["file"]).exists():
            sent = await bot.send_video_note(
                chat_id,
                FSInputFile(FILES_DIR / block["file"]),
                reply_markup=keyboard,
            )
            LAST_BOT_MESSAGE[user_id] = sent
        else:
            await show_text(bot, chat_id, user_id, f"[кружок ещё не загружен в data/files: {block['file']}]", None, False)

    elif block["type"] == "document":
        file_names = block["file"] if isinstance(block["file"], list) else [block["file"]]
        missing = [name for name in file_names if not (FILES_DIR / name).exists()]
        single_image = len(file_names) == 1 and (FILES_DIR / file_names[0]).suffix.lower() in IMAGE_EXTENSIONS
        if missing:
            missing_list = ", ".join(missing)
            text = f"{block['text']}\n\n[файлы ещё не загружены в data/files: {missing_list}]"
            await show_text(bot, chat_id, user_id, text, keyboard, should_replace, parse_mode)
        elif single_image:
            sent = await send_file_with_caption(
                bot, chat_id, FILES_DIR / file_names[0], block["text"], keyboard, parse_mode
            )
            LAST_BOT_MESSAGE[user_id] = sent
        else:
            await show_text(bot, chat_id, user_id, block["text"], keyboard, should_replace, parse_mode)
            for name in file_names:
                await send_file(bot, chat_id, FILES_DIR / name)

    if block_id == CONSULTATION_DONE_BLOCK:
        # Заявка оформляется только после того, как сообщение юзеру реально
        # доставлено (если отправка упала, мы сюда не дойдём), и не задерживает
        # цепочку: уведомление в чат и лид в Битрикс уходят параллельно.
        await set_tag_by_name(user_id, TAG_CONSULTATION_DONE)
        run_in_background(notify_consultation_lead(bot, "Telegram", user_id))
        run_in_background(send_lead_to_bitrix("Telegram", user_id))

    if block.get("auto_next"):
        # auto_next — следующее звено той же цепочки сообщений, а не переход
        # по кнопке, поэтому шлём новым сообщением, не трогая предыдущее.
        delay = block.get("auto_next_delay", AUTO_NEXT_DELAY_SECONDS)
        if delay:
            await bot.send_chat_action(chat_id, "typing")
            await asyncio.sleep(delay)
        # auto_next может быть списком — так из одного блока запускаются
        # параллельные цепочки (например, напоминания и безусловная доставка).
        targets = block["auto_next"] if isinstance(block["auto_next"], list) else [block["auto_next"]]
        for target in targets:
            await render_block(bot, chat_id, user_id, target, replace=False, activity=activity)
