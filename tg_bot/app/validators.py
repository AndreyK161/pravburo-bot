import re


def validate_phone(text: str) -> str | None:
    """Возвращает номер в формате 8XXXXXXXXXX (11 цифр) или None, если это не похоже на телефон.

    Принимает +7…, 7…, 8…, с пробелами, скобками и дефисами в любом месте."""
    digits = re.sub(r"\D", "", text)
    if len(digits) == 11 and digits[0] in ("7", "8"):
        return "8" + digits[1:]
    return None


def parse_referral_contact(text: str | None) -> tuple[str, str] | None:
    """Имя и один российский телефон; чужие данные не пишутся в профиль партнёра."""
    if not text:
        return None
    candidates = list(re.finditer(r"(?<![\w+])(?:\+7|[78])(?:[\s()–—.-]*\d){10}(?![\s()–—.-]*\d)", text))
    if len(candidates) != 1:
        return None
    match = candidates[0]
    phone = validate_phone(match.group())
    name = (text[:match.start()] + " " + text[match.end():]).strip(" ,;:\n\t-–—")
    if not phone or not name or len(name) > 200 or not any(c.isalpha() for c in name):
        return None
    if any(c.isdigit() for c in name):
        return None
    return name, phone


# save_as/validate из scenario.json ссылаются на эти функции по имени.
VALIDATORS = {
    "phone": validate_phone,
}
