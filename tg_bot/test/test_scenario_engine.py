import asyncio
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest

import scenario_engine
import database
import state
from scheduler import process_due_steps
from scenario_engine import build_keyboard, render_block


async def let_background_tasks_run() -> None:
    """Ждём, пока фоновая asyncio.create_task отработает — с реальной БД внутри
    неё настоящий сетевой round-trip, поэтому нужен не просто холостой тик цикла
    событий, а немного настоящего времени."""
    await asyncio.sleep(0.2)


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
            "fork": {
                "type": "message",
                "text": "Развилка",
                "auto_next": ["fork_reminder", "fork_always"],
            },
            "fork_reminder": {"type": "delay", "seconds": 0, "next": "chained_b"},
            "fork_always": {"type": "delay", "seconds": 0, "always": True, "next": "welcome"},
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


async def test_quiz_result_routes_by_score_ranges(bot, scenario, monkeypatch):
    scenario["blocks"]["result"] = {
        "type": "quiz_result",
        "ranges": [{"max": 3, "next": "welcome"}],
        "default": "chained_b",
    }
    for score, expected in [(0, "Привет!"), (3, "Привет!"), (4, "Второе сообщение цепочки")]:
        bot.send_message.reset_mock()

        async def fake_score(user_id, prefix="", score=score):
            return score

        monkeypatch.setattr(scenario_engine, "get_quiz_score", fake_score)
        await render_block(bot, chat_id=1, user_id=42, block_id="result", replace=False)
        assert bot.send_message.call_args[0][1] == expected


# --- отложенные шаги (delay-блоки хранятся в БД, отправляет планировщик) ---

async def _ensure_user(user_id: int = 42) -> None:
    async with database.DB_POOL.acquire() as conn:
        await conn.execute("DELETE FROM scheduled_steps WHERE user_id = $1", user_id)
        await conn.execute(
            "INSERT INTO tg_users (user_id, chat_id) VALUES ($1, 1) "
            "ON CONFLICT (user_id) DO UPDATE SET last_activity_at = NULL",
            user_id,
        )


async def test_delay_block_sends_when_user_inactive(bot, scenario):
    await _ensure_user()
    await render_block(bot, chat_id=1, user_id=42, block_id="waiter")
    bot.send_message.assert_not_awaited()  # пауза только запланирована

    assert await process_due_steps(bot) == 1
    bot.send_message.assert_awaited_once()
    assert bot.send_message.call_args[0][1] == "Привет!"


async def test_delay_block_skips_if_user_became_active(bot, scenario):
    await _ensure_user()
    await render_block(bot, chat_id=1, user_id=42, block_id="waiter")
    await database.record_activity(42)  # юзер успел что-то нажать, пока шаг ждал
    await process_due_steps(bot)

    bot.send_message.assert_not_awaited()


async def test_always_delay_ignores_activity(bot, scenario):
    await _ensure_user()
    await render_block(bot, chat_id=1, user_id=42, block_id="fork_always")
    await database.record_activity(42)
    await process_due_steps(bot)

    assert bot.send_message.call_args[0][1] == "Привет!"


async def test_step_survives_restart_and_is_not_sent_twice(bot, scenario):
    await _ensure_user()
    await render_block(bot, chat_id=1, user_id=42, block_id="waiter")
    # "перезапуск": память бота пуста, но шаг лежит в БД
    state.LAST_BOT_MESSAGE.clear()
    await process_due_steps(bot)
    await process_due_steps(bot)

    bot.send_message.assert_awaited_once()


async def test_click_during_auto_next_pause_still_cancels_reminder(bot, scenario, monkeypatch):
    # Юзер нажал кнопку в окне между показом блока и стартом паузы (auto_next
    # ждёт AUTO_NEXT_DELAY) — напоминание всё равно должно отмениться.
    await _ensure_user()
    monkeypatch.setattr(scenario_engine, "AUTO_NEXT_DELAY_SECONDS", 0.05)
    task = asyncio.create_task(render_block(bot, chat_id=1, user_id=42, block_id="fork"))
    await asyncio.sleep(0.01)
    await database.record_activity(42)
    await task
    await process_due_steps(bot)

    texts = [c[0][1] for c in bot.send_message.call_args_list]
    assert "Второе сообщение цепочки" not in texts
    assert "Привет!" in texts  # always-пауза из той же развилки сработала


async def test_failed_step_is_retried_then_given_up(bot, scenario, monkeypatch):
    await _ensure_user()
    scenario["blocks"]["broken"] = {"type": "delay", "seconds": 0, "next": "no_such_block"}
    await render_block(bot, chat_id=1, user_id=42, block_id="broken")
    await process_due_steps(bot)  # KeyError внутри — шаг не теряется
    async with database.DB_POOL.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM scheduled_steps WHERE user_id = 42")
    assert status == "pending"


def test_build_keyboard_puts_buttons_per_row():
    buttons = [{"text": "Да", "next": "a"}, {"text": "Нет", "next": "b"}, {"text": "Ещё", "next": "c"}]

    assert [len(r) for r in build_keyboard(buttons).inline_keyboard] == [1, 1, 1]
    assert [len(r) for r in build_keyboard(buttons, 2).inline_keyboard] == [2, 1]


async def test_same_pending_step_is_not_scheduled_twice(bot, scenario):
    await _ensure_user()
    await render_block(bot, chat_id=1, user_id=42, block_id="waiter")
    await render_block(bot, chat_id=1, user_id=42, block_id="waiter")  # повторное нажатие
    await process_due_steps(bot)

    bot.send_message.assert_awaited_once()


async def test_consultation_lead_is_sent_only_after_message_delivered(bot, scenario, monkeypatch):
    notify, bitrix = AsyncMock(), AsyncMock()
    monkeypatch.setattr(scenario_engine, "notify_consultation_lead", notify)
    monkeypatch.setattr(scenario_engine, "send_lead_to_bitrix", bitrix)
    monkeypatch.setattr(scenario_engine, "set_tag_by_name", AsyncMock())
    scenario["blocks"][scenario_engine.CONSULTATION_DONE_BLOCK] = {"type": "message", "text": "Спасибо", "buttons": []}

    await render_block(bot, chat_id=1, user_id=42, block_id=scenario_engine.CONSULTATION_DONE_BLOCK, replace=False)
    await let_background_tasks_run()
    notify.assert_awaited_once()
    bitrix.assert_awaited_once()

    # доставка не удалась — заявка не создаётся
    notify.reset_mock()
    bitrix.reset_mock()
    bot.send_message.side_effect = TelegramBadRequest(method=AsyncMock(), message="boom")
    with pytest.raises(TelegramBadRequest):
        await render_block(bot, chat_id=1, user_id=42, block_id=scenario_engine.CONSULTATION_DONE_BLOCK, replace=False)
    notify.assert_not_awaited()
    bitrix.assert_not_awaited()
