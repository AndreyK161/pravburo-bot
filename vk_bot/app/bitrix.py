import aiohttp

from config import BITRIX_SOURCE_ID_VK, BITRIX_WEBHOOK_URL
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


def _build_lead_fields(platform: str, user_id: int, lead: dict) -> dict:
    contact = f"@{lead['username']}" if lead.get("username") else f"id{user_id}"
    comments = (
        f"Платформа: {platform}\n"
        f"Регион: {lead.get('region') or '—'}\n"
        f"Имущество: {_format_has_property(lead.get('has_property'))}\n"
        f"Контакт: {contact}\n"
        f"Источник: {_format_source(lead.get('source'), lead.get('utm_source'), lead.get('utm_campaign'))}"
    )
    fields = {
        "TITLE": f"Заявка на консультацию ({platform})",
        "NAME": lead.get("name") or "",
        "COMMENTS": comments,
    }
    if lead.get("phone"):
        fields["PHONE"] = [{"VALUE": lead["phone"], "VALUE_TYPE": "WORK"}]
    if BITRIX_SOURCE_ID_VK:
        fields["SOURCE_ID"] = BITRIX_SOURCE_ID_VK
    return fields


async def send_lead_to_bitrix(platform: str, user_id: int) -> None:
    if not BITRIX_WEBHOOK_URL:
        print(f"[bitrix] BITRIX_WEBHOOK_URL не задан — лид для user_id={user_id} не отправлен")
        return
    lead = await get_consultation_lead(user_id)
    if lead is None:
        return

    fields = _build_lead_fields(platform, user_id, lead)
    url = f"{BITRIX_WEBHOOK_URL.rstrip('/')}/crm.lead.add.json"
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json={"fields": fields}) as resp:
                body = await resp.json(content_type=None)
                if resp.status != 200 or "error" in body:
                    print(f"[bitrix] не удалось создать лид: {body}")
                else:
                    print(f"[bitrix] лид создан: {body}")
    except aiohttp.ClientError as e:
        # Битрикс недоступен/сеть моргнула — не должно ронять показ блока пользователю.
        print(f"[bitrix] ошибка запроса к Битрикс24: {e}")
