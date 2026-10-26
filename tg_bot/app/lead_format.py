"""Текст заявки на консультацию — один формат и для карточки в Битрикс, и для уведомления в чат."""
import json

from config import SCENARIO_PATH

# Префикс ключей в tg_users.quiz_answers -> название ветки/квиза (ключи ответов
# первого квиза: q1..q5; у квиза второй ветки будут свои, с префиксом "c").
QUIZ_BRANCH_LABELS = {
    "q": "Ветка 1: плачу вовремя, но тяжело",
    "c": "Ветка 2: коллекторы",
    "b": "Ветка 3: приставы",
}


def load_scenario() -> dict:
    # Читаем файл при формировании заявки, а не импортируем scenario_engine
    # (он сам импортирует модули отправки заявок — получился бы циклический импорт).
    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def format_source(source: str | None, utm_source: str | None, utm_campaign: str | None) -> str:
    if utm_source:
        return f"{utm_source} / {utm_campaign}" if utm_campaign else utm_source
    return source or "—"


def format_quiz_branch(answers: dict) -> str:
    if answers.get("service_mfc") == 1:
        return QUIZ_BRANCH_LABELS["b"]
    labels = [label for prefix, label in QUIZ_BRANCH_LABELS.items() if any(k.startswith(prefix) for k in answers)]
    return "; ".join(labels) if labels else "квиз не проходил"


def format_quiz_answers(answers: dict, scenario: dict) -> list[str]:
    """Строки вида "Вопрос — выбранный ответ" в порядке прохождения квиза.

    Ответ ищется по сценарию: кнопка, у которой quiz_question и quiz_score совпали
    с сохранёнными. Если сценарий потом поменяли и совпадения нет, пишем баллы."""
    # Служебный выбор дохода нужен только для маршрутизации сценария, не для CRM.
    answers = {key: value for key, value in answers.items() if key not in {"route_income", "service_mfc"}}
    lines = []
    seen = set()
    for block in scenario["blocks"].values():
        for button in block.get("buttons", []):
            question = button.get("quiz_question")
            if question in answers and question not in seen and button.get("quiz_score") == answers[question]:
                lines.append((question, f"{block['text']} — {button['text']}"))
                seen.add(question)
                break
    known = {q for q, _ in lines}
    lines.extend((q, f"{q} — {score} б. (ответ не найден в сценарии)") for q, score in answers.items() if q not in known)
    return [line for _, line in sorted(lines, key=lambda x: x[0])]


def format_lead_comment(platform: str, user_id: int, lead: dict, scenario: dict | None = None) -> str:
    scenario = scenario or load_scenario()
    answers = lead.get("quiz_answers") or {}
    if isinstance(answers, str):
        answers = json.loads(answers)
    contact = f"@{lead['username']}" if lead.get("username") else f"id{user_id}"
    parts = [
        f"Платформа: {platform}",
        f"Контакт: {contact}",
        f"Telegram ID: {user_id}",
        f"Start-параметр: {lead.get('source') or '—'}",
        f"Источник: {format_source(lead.get('source'), lead.get('utm_source'), lead.get('utm_campaign'))}",
        f"Ветка квиза: {format_quiz_branch(answers)}",
    ]
    if answers.get("service_mfc") == 1:
        parts.append("Услуга: МФЦ")
    if lead.get("username") and platform == "Telegram":
        parts.append(f"Ссылка на пользователя: https://t.me/{lead['username']}")
    elif platform == "Telegram":
        parts.append("Ссылка на пользователя: недоступна — username не указан; используйте телефон")
    answer_lines = format_quiz_answers(answers, scenario)
    if answer_lines:
        parts.append("Ответы:\n" + "\n".join(f"{i}. {line}" for i, line in enumerate(answer_lines, 1)))
    return "\n".join(parts)
