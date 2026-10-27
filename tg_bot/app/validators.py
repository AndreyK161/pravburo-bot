import re


def validate_phone(text: str) -> str | None:
    """Возвращает номер в формате 8XXXXXXXXXX (11 цифр) или None, если это не похоже на телефон.

    Принимает +7…, 7…, 8…, с пробелами, скобками и дефисами в любом месте."""
    digits = re.sub(r"\D", "", text)
    if len(digits) == 11 and digits[0] in ("7", "8"):
        return "8" + digits[1:]
    return None


def validate_name(text: str | None) -> str | None:
    """Имя или ФИО, без телефона, цифр, ссылок и произвольных символов."""
    if not text:
        return None
    name = re.sub(r"\s+", " ", text).strip(" ,;:\t\n")
    if not name or len(name) > 200 or not any(c.isalpha() for c in name):
        return None
    if not all(c.isalpha() or c in " -'’." for c in name):
        return None
    return name


def parse_contact(text: str | None) -> tuple[str | None, str] | None:
    """Один телефон с необязательным именем до/после него.

    Не принимает два номера или лишние цифры: нельзя склеивать их в один контакт.
    Номер приводится к 8XXXXXXXXXX.
    """
    if not text:
        return None
    candidates = list(re.finditer(r"(?<![\w+])(?:\+7|[78])(?:[\s()–—.-]*\d){10}(?![\s()–—.-]*\d)", text))
    if len(candidates) != 1:
        return None
    match = candidates[0]
    phone = validate_phone(match.group())
    raw_name = (text[:match.start()] + " " + text[match.end():]).strip(" ,;:\n\t-–—")
    name = validate_name(raw_name) if raw_name else None
    if not phone or (raw_name and name is None):
        return None
    return name, phone


def parse_referral_contact(text: str | None) -> tuple[str, str] | None:
    """Для знакомого обязательны и имя, и телефон в одном сообщении."""
    contact = parse_contact(text)
    if contact is None or contact[0] is None:
        return None
    return contact[0], contact[1]


# save_as/validate из scenario.json ссылаются на эти функции по имени.
VALIDATORS = {
    "phone": validate_phone,
}
