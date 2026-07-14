import re


def validate_phone(text: str) -> str | None:
    """Возвращает номер в формате +7XXXXXXXXXX или None, если это не похоже на телефон."""
    digits = re.sub(r"\D", "", text)
    if len(digits) == 11 and digits[0] in ("7", "8"):
        return "+7" + digits[1:]
    return None


# save_as/validate из scenario.json ссылаются на эти функции по имени.
VALIDATORS = {
    "phone": validate_phone,
}
