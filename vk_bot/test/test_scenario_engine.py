import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from vkbottle.exception_factory import VKAPIError

import scenario_engine
import state
from scenario_engine import build_keyboard, render_block


async def let_background_tasks_run() -> None:
    """Ждём, пока фоновая asyncio.create_task отработает — с реальной БД внутри
    неё настоящий сетевой round-trip, поэтому нужен не просто холостой тик цикла
    событий, а немного настоящего времени."""
    await asyncio.sleep(0.2)


def test_build_keyboard_empty():
    assert build_keyboard([]) is None


def test_build_keyboard_builds_one_row_per_button():
    keyboard = json.loads(build_keyboard([
        {"text": "Раз", "next": "a"},
        {"text": "Два", "next": "b"},
    ]))
    rows = keyboard["buttons"]
    assert len(rows) == 2
    assert rows[0][0]["action"]["label"] == "Раз"
    assert rows[0][0]["action"]["payload"] == {"block": "a"}
    assert rows[1][0]["action"]["label"] == "Два"
    assert rows[1][0]["action"]["payload"] == {"block": "b"}
    # Кнопка обязана быть type=callback, а не text — иначе клик по ней придёт
    # как обычное message_new, а не message_event, и message_event_handler
    # его не увидит (реальный баг, который тесты без этой проверки не ловили).
    assert rows[0][0]["action"]["type"] == "callback"
    assert rows[1][0]["action"]["type"] == "callback"


def test_build_keyboard_packs_rows_to_stay_within_vk_limits():
    # VK Bot API отвергает inline-клавиатуру больше 6 строк по 5 кнопок
    # ("Keyboard format is invalid: buttons contain too much rows") — при
    # большом числе кнопок (как в реальном блоке general_menu) их нужно
    # паковать плотнее, а не класть по одной в строку.
    buttons = [{"text": f"Кнопка {i}", "next": f"b{i}"} for i in range(10)]
    keyboard = json.loads(build_keyboard(buttons))
    rows = keyboard["buttons"]

    assert len(rows) <= 6
    assert all(len(row) <= 5 for row in rows)
    assert sum(len(row) for row in rows) == 10


def test_build_keyboard_set_field_button():
    keyboard = json.loads(build_keyboard([
        {"text": "Да", "next": "x", "set_field": "has_property", "set_value": "yes"},
    ]))
    action = keyboard["buttons"][0][0]["action"]
    assert action["label"] == "Да"
    assert action["payload"] == {"field": "has_property", "value": "yes", "block": "x"}


@pytest.fixture
def scenario(monkeypatch):
    """Небольшой тестовый сценарий вместо продовых data/scenario.json."""
    test_scenario = {
        "start": "welcome",
        "blocks": {
            "welcome": {
                "type": "message",
                "text": "Привет!",
                "buttons": [{"text": "Дальше", "next": "welcome"}],
            },
            "gate": {
                "type": "condition",
                "vk_channel": "12345",
                "yes": "welcome",
                "no": "denied",
            },
            "denied": {
                "type": "message",
                "text": "Подпишитесь",
                "buttons": [],
            },
            "ask_name": {
                "type": "input",
                "text": "Как вас зовут?",
                "save_as": "name",
                "next": "welcome",
            },
            "chained_a": {
                "type": "message",
                "text": "Первое сообщение цепочки",
                "auto_next": "chained_b",
            },
            "chained_b": {
                "type": "message",
                "text": "Второе сообщение цепочки",
                "buttons": [],
            },
            "waiter": {
                "type": "delay",
                "seconds": 0,
                "next": "welcome",
            },
        },
    }
    monkeypatch.setattr(scenario_engine, "SCENARIO", test_scenario)
    return test_scenario


async def test_message_block_sends_new_message_when_no_prior(vk_api, scenario):
    vk_api.messages.send.return_value = 111

    await render_block(vk_api, peer_id=1, user_id=42, block_id="welcome")

    vk_api.messages.send.assert_awaited_once()
    kwargs = vk_api.messages.send.call_args.kwargs
    assert kwargs["peer_id"] == 1
    assert kwargs["message"] == "Привет!"
    assert state.LAST_BOT_MESSAGE[42] == {"peer_id": 1, "message_id": 111}


async def test_message_block_edits_prior_message_when_replacing(vk_api, scenario):
    state.LAST_BOT_MESSAGE[42] = {"peer_id": 1, "message_id": 555}

    await render_block(vk_api, peer_id=1, user_id=42, block_id="welcome", replace=True)

    vk_api.messages.edit.assert_awaited_once()
    vk_api.messages.send.assert_not_awaited()
    assert state.LAST_BOT_MESSAGE[42] == {"peer_id": 1, "message_id": 555}


async def test_edit_error_falls_back_to_new_message(vk_api, scenario):
    # У VK нет отдельного "не изменилось", как у Telegram — любая ошибка edit
    # (сообщение устарело/удалено и т.п.) должна просто откатываться на новое сообщение.
    state.LAST_BOT_MESSAGE[42] = {"peer_id": 1, "message_id": 555}
    vk_api.messages.edit.side_effect = VKAPIError(error_msg="too old")
    vk_api.messages.send.return_value = 999

    await render_block(vk_api, peer_id=1, user_id=42, block_id="welcome", replace=True)

    vk_api.messages.send.assert_awaited_once()
    assert state.LAST_BOT_MESSAGE[42] == {"peer_id": 1, "message_id": 999}


async def test_never_replace_block_always_sends_new_message(vk_api, scenario, monkeypatch):
    monkeypatch.setattr(scenario_engine, "NEVER_REPLACE_BLOCK", "welcome")
    state.LAST_BOT_MESSAGE[42] = {"peer_id": 1, "message_id": 555}
    vk_api.messages.send.return_value = 777

    await render_block(vk_api, peer_id=1, user_id=42, block_id="welcome", replace=True)

    vk_api.messages.edit.assert_not_awaited()
    vk_api.messages.send.assert_awaited_once()


async def test_condition_block_subscribed_goes_to_yes_branch(vk_api, scenario):
    vk_api.groups.is_member.return_value = True
    vk_api.messages.send.return_value = 1

    await render_block(vk_api, peer_id=1, user_id=42, block_id="gate")

    vk_api.messages.send.assert_awaited_once()
    assert vk_api.messages.send.call_args.kwargs["message"] == "Привет!"


async def test_condition_block_not_subscribed_goes_to_no_branch(vk_api, scenario):
    vk_api.groups.is_member.return_value = False
    vk_api.messages.send.return_value = 1

    await render_block(vk_api, peer_id=1, user_id=42, block_id="gate")

    vk_api.messages.send.assert_awaited_once()
    assert vk_api.messages.send.call_args.kwargs["message"] == "Подпишитесь"


async def test_condition_block_treats_api_error_as_not_subscribed(vk_api, scenario):
    # Если groups.isMember упал (например, сообщество недоступно) — тоже
    # считаем "не подписан", а не роняем показ блока.
    vk_api.groups.is_member.side_effect = VKAPIError(error_msg="boom")
    vk_api.messages.send.return_value = 1

    await render_block(vk_api, peer_id=1, user_id=42, block_id="gate")

    assert vk_api.messages.send.call_args.kwargs["message"] == "Подпишитесь"


async def test_input_block_records_awaiting_state_and_does_not_advance(vk_api, scenario):
    vk_api.messages.send.return_value = 1

    await render_block(vk_api, peer_id=1, user_id=42, block_id="ask_name")

    assert state.AWAITING_INPUT[42] == {"save_as": "name", "next": "welcome", "validate": None}
    vk_api.messages.send.assert_awaited_once()
    assert vk_api.messages.send.call_args.kwargs["message"] == "Как вас зовут?"


async def test_auto_next_chains_to_next_block(vk_api, scenario, monkeypatch):
    monkeypatch.setattr(scenario_engine.asyncio, "sleep", AsyncMock())
    vk_api.messages.send.side_effect = [111, 222]

    await render_block(vk_api, peer_id=1, user_id=42, block_id="chained_a")

    assert vk_api.messages.send.await_count == 2
    texts = [call.kwargs["message"] for call in vk_api.messages.send.await_args_list]
    assert texts == ["Первое сообщение цепочки", "Второе сообщение цепочки"]


async def test_delay_block_continues_if_user_inactive(vk_api, scenario):
    # seconds=0 у блока "waiter" в тестовом сценарии — asyncio.sleep не патчим,
    # чтобы не мешать себе же дожидаться завершения фоновой задачи ниже.
    vk_api.messages.send.return_value = 1

    await render_block(vk_api, peer_id=1, user_id=42, block_id="waiter")
    await let_background_tasks_run()

    vk_api.messages.send.assert_awaited_once()
    assert vk_api.messages.send.call_args.kwargs["message"] == "Привет!"


async def test_delay_block_skips_if_user_became_active(vk_api, scenario):
    state.USER_ACTIVITY[42] = 0

    await render_block(vk_api, peer_id=1, user_id=42, block_id="waiter")
    state.USER_ACTIVITY[42] = 1  # юзер успел что-то нажать, пока бот "спал"
    await let_background_tasks_run()

    vk_api.messages.send.assert_not_awaited()


async def test_document_block_reports_missing_file(vk_api, monkeypatch, scenario):
    test_scenario = scenario_engine.SCENARIO
    test_scenario["blocks"]["missing_doc"] = {
        "type": "document",
        "text": "Вот файл",
        "file": "does_not_exist.pdf",
        "buttons": [],
    }
    vk_api.messages.send.return_value = 1

    await render_block(vk_api, peer_id=1, user_id=42, block_id="missing_doc")

    vk_api.messages.send.assert_awaited_once()
    assert "не загружены" in vk_api.messages.send.call_args.kwargs["message"]
