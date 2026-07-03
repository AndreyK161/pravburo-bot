from types import SimpleNamespace
from unittest.mock import AsyncMock

import handlers
import scenario_engine
import state


def make_message(user_id=1, chat_id=1, username="tester", text="/start"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id, username=username),
        chat=SimpleNamespace(id=chat_id),
        text=text,
    )


def make_callback(user_id=1, chat_id=1, data="block:general_menu"):
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
        data=data,
        answer=AsyncMock(),
    )
    return callback


async def test_command_start_handler_upserts_user_and_renders_start_block(bot, monkeypatch):
    upsert_user = AsyncMock()
    render_block = AsyncMock()
    monkeypatch.setattr(handlers, "upsert_user", upsert_user)
    monkeypatch.setattr(handlers, "render_block", render_block)

    message = make_message(user_id=7, chat_id=8, username="ivan")
    command = SimpleNamespace(args="YDX-DIRECT")

    await handlers.command_start_handler(message, bot, command)

    upsert_user.assert_awaited_once_with(7, 8, "ivan", "YDX-DIRECT")
    render_block.assert_awaited_once_with(bot, 8, 7, scenario_engine.SCENARIO["start"], replace=False)


async def test_command_start_handler_resets_awaiting_input(bot, monkeypatch):
    monkeypatch.setattr(handlers, "upsert_user", AsyncMock())
    monkeypatch.setattr(handlers, "render_block", AsyncMock())
    state.AWAITING_INPUT[7] = {"save_as": "name", "next": "welcome"}

    message = make_message(user_id=7)
    command = SimpleNamespace(args=None)

    await handlers.command_start_handler(message, bot, command)

    assert 7 not in state.AWAITING_INPUT


async def test_scenario_button_handler_delegates_to_render_block(bot, monkeypatch):
    render_block = AsyncMock()
    monkeypatch.setattr(handlers, "render_block", render_block)

    callback = make_callback(user_id=3, chat_id=4, data="block:general_menu")
    await handlers.scenario_button_handler(callback, bot)

    render_block.assert_awaited_once_with(bot, 4, 3, "general_menu")
    callback.answer.assert_awaited_once()


async def test_fallback_text_handler_sends_return_to_menu_when_nothing_pending(bot):
    message = make_message(user_id=5, chat_id=6, text="привет боту")

    await handlers.fallback_text_handler(message, bot)

    bot.send_message.assert_awaited_once()
    assert bot.send_message.call_args[0][1] == "Для возврата в главное меню нажмите ⬇️"


async def test_fallback_text_handler_saves_pending_input_and_advances(bot, monkeypatch):
    render_block = AsyncMock()
    save_user_field = AsyncMock()
    monkeypatch.setattr(handlers, "render_block", render_block)
    monkeypatch.setattr(handlers, "save_user_field", save_user_field)

    state.AWAITING_INPUT[5] = {"save_as": "name", "next": "consultation_menu"}
    message = make_message(user_id=5, chat_id=6, text="Иван")

    await handlers.fallback_text_handler(message, bot)

    assert state.USER_DATA[5]["name"] == "Иван"
    save_user_field.assert_awaited_once_with(5, "name", "Иван")
    render_block.assert_awaited_once_with(bot, 6, 5, "consultation_menu", replace=False)
    bot.send_message.assert_not_awaited()
    assert 5 not in state.AWAITING_INPUT


async def test_fallback_text_handler_rejects_invalid_phone_and_keeps_waiting(bot, monkeypatch):
    render_block = AsyncMock()
    save_user_field = AsyncMock()
    monkeypatch.setattr(handlers, "render_block", render_block)
    monkeypatch.setattr(handlers, "save_user_field", save_user_field)

    pending = {"save_as": "phone", "next": "consultation_contact", "validate": "phone"}
    state.AWAITING_INPUT[5] = pending
    message = make_message(user_id=5, chat_id=6, text="не номер телефона")

    await handlers.fallback_text_handler(message, bot)

    save_user_field.assert_not_awaited()
    render_block.assert_not_awaited()
    bot.send_message.assert_awaited_once()
    assert "номер телефона" in bot.send_message.call_args[0][1]
    assert state.AWAITING_INPUT[5] is pending  # ждём ввод повторно


async def test_fallback_text_handler_accepts_valid_phone_and_normalizes_it(bot, monkeypatch):
    render_block = AsyncMock()
    save_user_field = AsyncMock()
    monkeypatch.setattr(handlers, "render_block", render_block)
    monkeypatch.setattr(handlers, "save_user_field", save_user_field)

    state.AWAITING_INPUT[5] = {"save_as": "phone", "next": "consultation_contact", "validate": "phone"}
    message = make_message(user_id=5, chat_id=6, text="8 (999) 123-45-67")

    await handlers.fallback_text_handler(message, bot)

    assert state.USER_DATA[5]["phone"] == "+79991234567"
    save_user_field.assert_awaited_once_with(5, "phone", "+79991234567")
    render_block.assert_awaited_once_with(bot, 6, 5, "consultation_contact", replace=False)
    assert 5 not in state.AWAITING_INPUT
