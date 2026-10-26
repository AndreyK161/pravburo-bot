import json
import asyncio
import aiohttp
from zoneinfo import ZoneInfo

from config import BITRIX_SOURCE_ID_TG, BITRIX_WEBHOOK_URL
from database import get_consultation_lead
from database import claim_referral_for_bitrix, finish_referral_bitrix
from lead_format import format_lead_comment


def _build_referral_fields(referral: dict) -> dict:
    transferred_at = referral["created_at"].astimezone(ZoneInfo("Europe/Moscow")).isoformat()
    return {
        "TITLE": "Реферальный — рекомендация партнёра",
        "NAME": referral["contact_name"],
        "PHONE": [{"VALUE": referral["contact_phone"], "VALUE_TYPE": "WORK"}],
        "COMMENTS": (
            "Тип: реферальный\n"
            f"Имя знакомого: {referral['contact_name']}\n"
            f"Телефон знакомого: {referral['contact_phone']}\n"
            f"Telegram ID партнёра: {referral['partner_telegram_id']}\n"
            f"Имя партнёра: {referral['partner_name']}\n"
            f"Username партнёра: {referral.get('partner_username') or '—'}\n"
            f"Дата передачи (МСК): {transferred_at}\n"
            f"Метка: {referral['marker']}\n"
            f"ID рекомендации: {referral['id']}"
        ),
    }


async def send_referral_to_bitrix(referral: dict) -> None:
    # При локальном запуске пустой webhook запрещает любые внешние отправки.
    if not BITRIX_WEBHOOK_URL:
        return
    if not await claim_referral_for_bitrix(referral["id"]):
        return
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(
                f"{BITRIX_WEBHOOK_URL.rstrip('/')}/crm.lead.add.json",
                json={"fields": _build_referral_fields(referral)},
            ) as response:
                body = await response.json(content_type=None)
                if response.status == 200 and body.get("result") and not body.get("error"):
                    await finish_referral_bitrix(referral["id"], "sent", int(body["result"]))
                else:
                    await finish_referral_bitrix(referral["id"], "failed")
                    print(f"[referral] Битрикс отклонил рекомендацию id={referral['id']}")
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        # При обрыве ответа неизвестно, создался ли лид: автоматически не дублируем.
        await finish_referral_bitrix(referral["id"], "unknown")
        print(f"[referral] требуется проверка доставки рекомендации id={referral['id']}")


def _build_lead_fields(platform: str, user_id: int, lead: dict) -> dict:
    # Имя в карточке — Telegram-username (других имён бот сейчас не собирает).
    name = f"@{lead['username']}" if lead.get("username") else f"id{user_id}"
    fields = {
        "TITLE": f"Заявка на консультацию ({platform})",
        "NAME": name,
        "COMMENTS": format_lead_comment(platform, user_id, lead),
    }
    answers = lead.get("quiz_answers") or {}
    if isinstance(answers, str):
        answers = json.loads(answers)
    if answers.get("service_mfc") == 1:
        fields["TITLE"] = f"Услуга МФЦ — заявка ({platform})"
    if lead.get("phone"):
        fields["PHONE"] = [{"VALUE": lead["phone"], "VALUE_TYPE": "WORK"}]
    if BITRIX_SOURCE_ID_TG:
        fields["SOURCE_ID"] = BITRIX_SOURCE_ID_TG
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
