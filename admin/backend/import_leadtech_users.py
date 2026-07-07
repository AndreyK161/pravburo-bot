import asyncio
import json
import re
import sys
from datetime import datetime

import asyncpg

from config import DATABASE_URL

SOURCE_LABEL = "leadtech_import"


def normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in ("7", "8"):
        return "+7" + digits[1:]
    return None


def variable_value(record: dict, name: str) -> str | None:
    for v in record.get("variables") or []:
        if v.get("name") == name and v.get("value"):
            return v["value"]
    return None


def normalize_property(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.strip().lower()
    if text.startswith("да"):
        return "yes"
    if text.startswith("нет"):
        return "no"
    return None  # свободный текст вида "Автокредит есть..." — не разобрать однозначно


def to_row(record: dict) -> tuple | None:
    telegram_id = record.get("telegram_id")
    if not telegram_id:
        return None  # контакт из вконтакте и т.п. — без telegram_id нашему боту он не нужен

    user_id = int(telegram_id)
    phone = normalize_phone(record.get("phone") or variable_value(record, "Номер телефона"))
    region = variable_value(record, "живет в") or variable_value(record, "Прописка")
    name = (record.get("name") or "").strip() or None
    created_at = datetime.fromisoformat(record["created_at"]) if record.get("created_at") else None
    has_property = normalize_property(variable_value(record, "Имущество"))
    # unsubscribed_at — отписка/блокировка старого бота на ЛидТехе. Не то же самое,
    # что блокировка именно нашего бота, но это единственный сигнал, что есть в экспорте.
    is_blocked = bool(record.get("unsubscribed_at"))

    return (
        user_id,
        user_id,  # chat_id — для личных чатов в телеграме совпадает с user_id
        record.get("telegram_username"),
        name,
        phone,
        region,
        SOURCE_LABEL,
        created_at,
        is_blocked,
        has_property,
    )


async def main() -> None:
    if len(sys.argv) < 2:
        print("Использование: python import_leadtech_users.py /путь/до/contacts.json")
        return

    with open(sys.argv[1], encoding="utf-8") as f:
        records = json.load(f)

    rows = {}
    skipped = 0
    for record in records:
        row = to_row(record)
        if row is None:
            skipped += 1
            continue
        rows[row[0]] = row  # dict по user_id — если в файле дубли telegram_id, останется последний

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        inserted = 0
        for row in rows.values():
            result = await conn.execute(
                """
                INSERT INTO users
                    (user_id, chat_id, username, name, phone, region, source, created_at, is_blocked, has_property)
                VALUES ($1, $2, $3, $4, $5, $6, $7, COALESCE($8, now()), $9, $10)
                ON CONFLICT (user_id) DO NOTHING
                """,
                *row,
            )
            if result.endswith(" 1"):
                inserted += 1
    finally:
        await conn.close()

    print(f"Всего записей в файле: {len(records)}")
    print(f"Без telegram_id (пропущены): {skipped}")
    print(f"Уникальных telegram-контактов: {len(rows)}")
    print(f"Реально добавлено новых: {inserted}")
    print(f"Уже существовали в базе (пропущены при вставке): {len(rows) - inserted}")


if __name__ == "__main__":
    asyncio.run(main())
