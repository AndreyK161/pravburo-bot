import json

from bitrix import _build_lead_fields
from lead_format import format_lead_comment

SCENARIO = {
    "blocks": {
        "quiz_q1": {
            "text": "Вопрос 1. Вы знаете точную сумму всех своих кредитов?",
            "buttons": [
                {"text": "Да, до рубля", "next": "x", "quiz_question": "q1", "quiz_score": 0},
                {"text": "Знаю примерно", "next": "x", "quiz_question": "q1", "quiz_score": 1},
            ],
        },
        "quiz_q2": {
            "text": "Вопрос 2. Брали ли вы новый кредит, чтобы внести платёж по старому?",
            "buttons": [
                {"text": "Нет", "next": "x", "quiz_question": "q2", "quiz_score": 0},
                {"text": "Так делаю постоянно", "next": "x", "quiz_question": "q2", "quiz_score": 10},
            ],
        },
    }
}


def make_lead(**kw):
    lead = {"username": "ivan", "phone": "89005555555", "source": "kollektory_vk_1", "utm_source": None,
            "utm_campaign": None, "quiz_answers": json.dumps({"q1": 1, "q2": 10})}
    lead.update(kw)
    return lead


def test_comment_contains_branch_source_contact_and_readable_answers():
    text = format_lead_comment("Telegram", 7, make_lead(), SCENARIO)

    assert "Контакт: @ivan" in text
    assert "Источник: kollektory_vk_1" in text
    assert "Ветка квиза: Ветка 1: плачу вовремя, но тяжело" in text
    assert "1. Вопрос 1. Вы знаете точную сумму всех своих кредитов? — Знаю примерно" in text
    assert "2. Вопрос 2. Брали ли вы новый кредит, чтобы внести платёж по старому? — Так делаю постоянно" in text


def test_comment_without_quiz_says_so():
    text = format_lead_comment("Telegram", 7, make_lead(quiz_answers="{}"), SCENARIO)

    assert "Ветка квиза: квиз не проходил" in text
    assert "Ответы:" not in text


def test_answer_missing_in_scenario_falls_back_to_score():
    text = format_lead_comment("Telegram", 7, make_lead(quiz_answers=json.dumps({"q1": 5})), SCENARIO)

    assert "q1 — 5 б." in text


def test_bitrix_fields_have_username_phone_and_comments(monkeypatch):
    import lead_format
    monkeypatch.setattr(lead_format, "load_scenario", lambda: SCENARIO)
    fields = _build_lead_fields("Telegram", 7, make_lead())

    assert fields["NAME"] == "@ivan"
    assert fields["PHONE"] == [{"VALUE": "89005555555", "VALUE_TYPE": "WORK"}]
    assert "Ветка квиза" in fields["COMMENTS"]


def test_comment_has_user_link_and_raw_start_parameter():
    text = format_lead_comment("Telegram", 7, make_lead(utm_source="vk", utm_campaign="1"), SCENARIO)
    assert "Start-параметр: kollektory_vk_1" in text
    assert "Источник: vk / 1" in text
    assert "Ссылка на пользователя: https://t.me/ivan" in text
    assert "Telegram ID: 7" in text


def test_without_username_no_fake_dialog_link():
    text = format_lead_comment("Telegram", 7, make_lead(username=None), SCENARIO)
    assert "username не указан" in text
    assert "https://t.me/" not in text


