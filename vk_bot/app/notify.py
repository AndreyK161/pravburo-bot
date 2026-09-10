import aiohttp

from config import NOTIFY_BOT_TOKEN, NOTIFY_CHAT_IDS
from database import get_consultation_lead

TELEGRAM_SEND_MESSAGE_URL = "https://api.telegram.org/bot{token}/sendMessage"


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


async def notify_consultation_lead(platform: str, user_id: int) -> None:
    if not NOTIFY_CHAT_IDS or not NOTIFY_BOT_TOKEN:
        return
    lead = await get_consultation_lead(user_id)
    if lead is None:
        return

    text = _format_lead_text(platform, user_id, lead)
    url = TELEGRAM_SEND_MESSAGE_URL.format(token=NOTIFY_BOT_TOKEN)
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for chat_id in NOTIFY_CHAT_IDS:
            try:
                async with session.post(url, json={"chat_id": chat_id, "text": text}) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        print(f"[notify] не удалось отправить уведомление в чат {chat_id}: {body}")
            except aiohttp.ClientError as e:
                # Чат недоступен/сеть моргнула — не должно ронять показ блока пользователю.
                print(f"[notify] ошибка отправки уведомления в чат {chat_id}: {e}")
