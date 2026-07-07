import asyncio
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest

import scenario_engine
import state
from scenario_engine import build_keyboard, render_block


async def let_background_tasks_run() -> None:
    """Несколько циклов событийного цикла — чтобы фоновая asyncio.create_task успела отработать."""
    for _ in range(5):
        await asyncio.sleep(0)


def test_build_keyboard_empty():
    assert build_keyboard([]) is None


def test_build_keyboard_builds_one_row_per_button():
    keyboard = build_keyboard([
        {"text": "Раз", "next": "a"},
        {"text": "Два", "next": "b"},
    ])
    rows = keyboard.inline_keyboard
    assert len(rows) == 2
    assert rows[0][0].text == "Раз"
    assert rows[0][0].callback_data == "block:a"
    assert rows[1][0].text == "Два"
    assert rows[1][0].callback_data == "block:b"


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
                "channel": "@test_channel",
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


async def test_message_block_sends_new_message_when_no_prior(bot, scenario):
    await render_block(bot, chat_id=1, user_id=42, block_id="welcome")

    bot.send_message.assert_awaited_once()
    args, kwargs = bot.send_message.call_args
    assert args[0] == 1
    assert args[1] == "Привет!"
    assert state.LAST_BOT_MESSAGE[42] is bot.send_message.return_value


async def test_message_block_edits_prior_message_when_replacing(bot, scenario):
    prior = AsyncMock()
    state.LAST_BOT_MESSAGE[42] = prior

    await render_block(bot, chat_id=1, user_id=42, block_id="welcome", replace=True)

    prior.edit_text.assert_awaited_once()
    bot.send_message.assert_not_awaited()
    assert state.LAST_BOT_MESSAGE[42] is prior.edit_text.return_value


async def test_message_not_modified_error_is_swallowed(bot, scenario):
    prior = AsyncMock()
    prior.edit_text.side_effect = TelegramBadRequest(method=AsyncMock(), message="message is not modified")
    state.LAST_BOT_MESSAGE[42] = prior

    await render_block(bot, chat_id=1, user_id=42, block_id="welcome", replace=True)

    # Ошибка "не изменилось" тихо проглатывается — новое сообщение не шлём
    bot.send_message.assert_not_awaited()


async def test_message_other_bad_request_falls_back_to_new_message(bot, scenario):
    prior = AsyncMock()
    prior.edit_text.side_effect = TelegramBadRequest(method=AsyncMock(), message="there is no text in the message")
    state.LAST_BOT_MESSAGE[42] = prior

    await render_block(bot, chat_id=1, user_id=42, block_id="welcome", replace=True)

    bot.send_message.assert_awaited_once()


async def test_never_replace_block_always_sends_new_message(bot, scenario, monkeypatch):
    monkeypatch.setattr(scenario_engine, "NEVER_REPLACE_BLOCK", "welcome")
    prior = AsyncMock()
    state.LAST_BOT_MESSAGE[42] = prior

    await render_block(bot, chat_id=1, user_id=42, block_id="welcome", replace=True)

    prior.edit_text.assert_not_awaited()
    bot.send_message.assert_awaited_once()


async def test_condition_block_subscribed_goes_to_yes_branch(bot, scenario):
    bot.get_chat_member.return_value = AsyncMock(status="member")

    await render_block(bot, chat_id=1, user_id=42, block_id="gate")

    bot.send_message.assert_awaited_once()
    assert bot.send_message.call_args[0][1] == "Привет!"


async def test_condition_block_not_subscribed_goes_to_no_branch(bot, scenario):
    bot.get_chat_member.return_value = AsyncMock(status="left")

    await render_block(bot, chat_id=1, user_id=42, block_id="gate")

    bot.send_message.assert_awaited_once()
    assert bot.send_message.call_args[0][1] == "Подпишитесь"


async def test_condition_block_treats_never_joined_as_not_subscribed(bot, scenario):
    # Если юзер никогда не состоял в канале (а не просто вышел), Telegram
    # кидает ошибку вместо статуса "left" — это тоже должно значить "не подписан".
    bot.get_chat_member.side_effect = TelegramBadRequest(method=AsyncMock(), message="member not found")

    await render_block(bot, chat_id=1, user_id=42, block_id="gate")

    bot.send_message.assert_awaited_once()
    assert bot.send_message.call_args[0][1] == "Подпишитесь"


async def test_input_block_records_awaiting_state_and_does_not_advance(bot, scenario):
    await render_block(bot, chat_id=1, user_id=42, block_id="ask_name")

    assert state.AWAITING_INPUT[42] == {"save_as": "name", "next": "welcome", "validate": None}
    bot.send_message.assert_awaited_once()
    assert bot.send_message.call_args[0][1] == "Как вас зовут?"


async def test_auto_next_chains_to_next_block(bot, scenario, monkeypatch):
    monkeypatch.setattr(scenario_engine.asyncio, "sleep", AsyncMock())

    await render_block(bot, chat_id=1, user_id=42, block_id="chained_a")

    assert bot.send_message.await_count == 2
    texts = [call.args[1] for call in bot.send_message.await_args_list]
    assert texts == ["Первое сообщение цепочки", "Второе сообщение цепочки"]


async def test_delay_block_continues_if_user_inactive(bot, scenario):
    # seconds=0 у блока "waiter" в тестовом сценарии — asyncio.sleep не патчим,
    # чтобы не мешать себе же дожидаться завершения фоновой задачи ниже.
    await render_block(bot, chat_id=1, user_id=42, block_id="waiter")
    await let_background_tasks_run()

    bot.send_message.assert_awaited_once()
    assert bot.send_message.call_args[0][1] == "Привет!"


async def test_delay_block_skips_if_user_became_active(bot, scenario):
    state.USER_ACTIVITY[42] = 0

    await render_block(bot, chat_id=1, user_id=42, block_id="waiter")
    state.USER_ACTIVITY[42] = 1  # юзер успел что-то нажать, пока бот "спал"
    await let_background_tasks_run()

    bot.send_message.assert_not_awaited()


async def test_document_block_reports_missing_file(bot, monkeypatch, scenario):
    test_scenario = scenario_engine.SCENARIO
    test_scenario["blocks"]["missing_doc"] = {
        "type": "document",
        "text": "Вот файл",
        "file": "does_not_exist.pdf",
        "buttons": [],
    }

    await render_block(bot, chat_id=1, user_id=42, block_id="missing_doc")

    bot.send_message.assert_awaited_once()
    assert "не загружены" in bot.send_message.call_args[0][1]
    bot.send_document.assert_not_awaited()
