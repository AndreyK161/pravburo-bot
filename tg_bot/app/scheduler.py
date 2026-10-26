import asyncio
import logging
from datetime import datetime, time, timedelta, timezone

from aiogram import Bot

from database import (
    claim_due_steps,
    defer_step_until,
    finish_step,
    get_last_activity,
    retry_step_later,
)
from config import REMINDER_END_HOUR, REMINDER_START_HOUR, REMINDER_TIMEZONE
from scenario_engine import render_block

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
MAX_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 60


def next_reminder_window(now: datetime | None = None) -> datetime | None:
    """Возвращает время следующего открытия окна 09:00–21:00.

    None означает, что сейчас окно открыто.
    """
    local_now = (now or datetime.now(timezone.utc)).astimezone(REMINDER_TIMEZONE)
    if REMINDER_START_HOUR <= local_now.hour < REMINDER_END_HOUR:
        return None
    opening_date = local_now.date()
    if local_now.hour >= REMINDER_END_HOUR:
        opening_date += timedelta(days=1)
    opening = datetime.combine(
        opening_date, time(REMINDER_START_HOUR), tzinfo=REMINDER_TIMEZONE
    )
    return opening.astimezone(timezone.utc)


async def process_due_steps(bot: Bot) -> int:
    """Отправляет все созревшие отложенные шаги. Возвращает, сколько обработано."""
    steps = await claim_due_steps()
    for step in steps:
        try:
            if not step["always"]:
                next_opening = next_reminder_window()
                if next_opening is not None:
                    await defer_step_until(step["id"], next_opening)
                    continue
            # Напоминание отменяется, если после старта цепочки юзер что-то делал.
            # Шаги с always (кружок, сообщения "через сутки") приходят в любом случае.
            if not step["always"]:
                last_activity = await get_last_activity(step["user_id"])
                if last_activity is not None and last_activity > step["chain_started_at"]:
                    await finish_step(step["id"], "cancelled")
                    continue
            await render_block(
                bot, step["chat_id"], step["user_id"], step["next_block_id"], replace=False
            )
            await finish_step(step["id"], "done")
        except Exception:
            logger.exception("Не удалось выполнить отложенный шаг %s", step["id"])
            if step["attempts"] >= MAX_ATTEMPTS:
                await finish_step(step["id"], "failed")
            else:
                await retry_step_later(step["id"], RETRY_DELAY_SECONDS)
    return len(steps)


async def run_scheduler(bot: Bot) -> None:
    # Фоновый цикл на всё время жизни бота; сбой одной итерации (например, обрыв БД)
    # не должен его останавливать.
    while True:
        try:
            await process_due_steps(bot)
        except Exception:
            logger.exception("Сбой итерации планировщика")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    defer_step_until,
