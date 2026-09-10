from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import NOTIFY_CHAT_IDS
from database import get_consultation_lead


def _format_has_property(value: str | None) -> str:
    if value == "yes":
        return "Да"
    if value == "no":
        return "Нет"
    return "—"


def _format_source(source: str | None, utm_source: str | None, utm_campaign: str | None) -> str:
    if utm_source:
        return f"{utm_source} / {utm_campaign}" if utm_campaign else utm_source
    return source or "—"


def _format_lead_text(platform: str, user_id: int, lead: dict) -> str:
    username = f"@{lead['username']}" if lead.get("username") else f"id{user_id}"
    return (
        "🆕 Новая заявка на консультацию\n"
        f"Платформа: {platform}\n"
        f"Имя: {lead.get('name') or '—'}\n"
        f"Телефон: {lead.get('phone') or '—'}\n"
        f"Регион: {lead.get('region') or '—'}\n"
        f"Имущество: {_format_has_property(lead.get('has_property'))}\n"
        f"Контакт: {username}\n"
        f"Источник: {_format_source(lead.get('source'), lead.get('utm_source'), lead.get('utm_campaign'))}"
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
