from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import NOTIFY_CHAT_IDS
from database import get_consultation_lead
from lead_format import format_lead_comment


def _format_lead_text(platform: str, user_id: int, lead: dict) -> str:
    return (
        "🆕 Новая заявка на консультацию\n"
        f"Телефон: {lead.get('phone') or '—'}\n"
        + format_lead_comment(platform, user_id, lead)
    )


async def notify_consultation_lead(bot: Bot, platform: str, user_id: int) -> None:
    if not NOTIFY_CHAT_IDS:
        return
    lead = await get_consultation_lead(user_id)
    if lead is None:
        return

    text = _format_lead_text(platform, user_id, lead)
    for chat_id in NOTIFY_CHAT_IDS:
        try:
            await bot.send_message(chat_id, text)
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            # Чат недоступен (бота не добавили/выгнали, неверный id и т.п.) —
            # это не должно ронять показ блока пользователю, просто пропускаем чат.
            print(f"[notify] не удалось отправить уведомление в чат {chat_id}: {e}")
