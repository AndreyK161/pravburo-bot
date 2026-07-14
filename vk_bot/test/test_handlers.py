import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import handlers
import scenario_engine
import state


def make_message(from_id=1, peer_id=1, text="привет", payload=None):
    return SimpleNamespace(
        from_id=from_id,
        peer_id=peer_id,
        text=text,
        payload=json.dumps(payload) if payload is not None else None,
    )


def make_message_event(user_id=1, peer_id=1, event_id="ev1", payload=None):
    obj = SimpleNamespace(user_id=user_id, peer_id=peer_id, event_id=event_id, payload=payload or {})
    return SimpleNamespace(object=obj)


async def test_handle_start_upserts_user_and_renders_start_block(vk_api, monkeypatch):
    monkeypatch.setattr(handlers.bot, "api", vk_api)
    upsert_user = AsyncMock()
    render_block = AsyncMock()
    monkeypatch.setattr(handlers, "upsert_user", upsert_user)
    monkeypatch.setattr(handlers, "render_block", render_block)

    message = make_message(from_id=7, peer_id=7)

    await handlers._handle_start(message, {"command": "start", "source": "YDX-DIRECT"})

    upsert_user.assert_awaited_once_with(7, 7, None, "YDX-DIRECT")
    render_block.assert_awaited_once_with(vk_api, 7, 7, scenario_engine.SCENARIO["start"], replace=False)


async def test_handle_start_resets_awaiting_input(vk_api, monkeypatch):
    monkeypatch.setattr(handlers.bot, "api", vk_api)
    monkeypatch.setattr(handlers, "upsert_user", AsyncMock())
    monkeypatch.setattr(handlers, "render_block", AsyncMock())
    state.AWAITING_INPUT[7] = {"save_as": "name", "next": "welcome"}

    message = make_message(from_id=7, peer_id=7)
    await handlers._handle_start(message, {"command": "start"})

    assert 7 not in state.AWAITING_INPUT


async def test_message_new_handler_routes_start_payload_to_handle_start(vk_api, monkeypatch):
    monkeypatch.setattr(handlers.bot, "api", vk_api)
    handle_start = AsyncMock()
    monkeypatch.setattr(handlers, "_handle_start", handle_start)

    message = make_message(from_id=9, peer_id=9, payload={"command": "start", "source": "vk_ads"})
    await handlers.message_new_handler(message)

    handle_start.assert_awaited_once()
    args = handle_start.call_args.args
    assert args[0] is message
    assert args[1] == {"command": "start", "source": "vk_ads"}


async def test_message_new_handler_routes_plain_text_to_fallback(vk_api, monkeypatch):
    monkeypatch.setattr(handlers.bot, "api", vk_api)
    handle_fallback = AsyncMock()
    monkeypatch.setattr(handlers, "_handle_fallback_text", handle_fallback)

    message = make_message(from_id=9, peer_id=9, text="просто текст")
    await handlers.message_new_handler(message)

    handle_fallback.assert_awaited_once_with(message)


async def test_message_event_handler_delegates_to_render_block(vk_api, monkeypatch):
    monkeypatch.setattr(handlers.bot, "api", vk_api)
    render_block = AsyncMock()
    gate_next_block = AsyncMock(return_value="general_menu")
    monkeypatch.setattr(handlers, "render_block", render_block)
    monkeypatch.setattr(handlers, "gate_next_block", gate_next_block)

    event = make_message_event(user_id=3, peer_id=4, event_id="ev9", payload={"block": "general_menu"})

    await handlers.message_event_handler(event)

    gate_next_block.assert_awaited_once_with(vk_api, 3, "general_menu")
    render_block.assert_awaited_once_with(vk_api, 4, 3, "general_menu")
    vk_api.messages.send_message_event_answer.assert_awaited_once_with(event_id="ev9", user_id=3, peer_id=4)


async def test_message_event_handler_saves_set_field_payload(vk_api, monkeypatch):
    monkeypatch.setattr(handlers.bot, "api", vk_api)
    render_block = AsyncMock()
    save_user_field = AsyncMock()
    gate_next_block = AsyncMock(return_value="consultation_offer_phone")
    monkeypatch.setattr(handlers, "render_block", render_block)
    monkeypatch.setattr(handlers, "save_user_field", save_user_field)
    monkeypatch.setattr(handlers, "gate_next_block", gate_next_block)

    event = make_message_event(
        user_id=3, peer_id=4, payload={"field": "has_property", "value": "yes", "block": "consultation_offer_phone"}
    )

    await handlers.message_event_handler(event)

    save_user_field.assert_awaited_once_with(3, "has_property", "yes")
    render_block.assert_awaited_once_with(vk_api, 4, 3, "consultation_offer_phone")


async def test_handle_fallback_text_sends_return_to_menu_when_nothing_pending(vk_api, monkeypatch):
    monkeypatch.setattr(handlers.bot, "api", vk_api)
    monkeypatch.setattr(handlers, "upsert_user", AsyncMock())
    vk_api.messages.send.return_value = 1

    message = make_message(from_id=5, peer_id=6, text="привет боту")

    await handlers._handle_fallback_text(message)

    vk_api.messages.send.assert_awaited_once()
    assert vk_api.messages.send.call_args.kwargs["message"] == "Для возврата в главное меню нажмите ⬇️"


async def test_handle_fallback_text_saves_pending_input_and_advances(vk_api, monkeypatch):
    monkeypatch.setattr(handlers.bot, "api", vk_api)
    render_block = AsyncMock()
    save_user_field = AsyncMock()
    monkeypatch.setattr(handlers, "render_block", render_block)
    monkeypatch.setattr(handlers, "save_user_field", save_user_field)

    state.AWAITING_INPUT[5] = {"save_as": "name", "next": "consultation_menu"}
    message = make_message(from_id=5, peer_id=6, text="Иван")

    await handlers._handle_fallback_text(message)

    assert state.USER_DATA[5]["name"] == "Иван"
    save_user_field.assert_awaited_once_with(5, "name", "Иван")
    render_block.assert_awaited_once_with(vk_api, 6, 5, "consultation_menu", replace=False)
    vk_api.messages.send.assert_not_awaited()
    assert 5 not in state.AWAITING_INPUT


async def test_handle_fallback_text_rejects_invalid_phone_and_keeps_waiting(vk_api, monkeypatch):
    monkeypatch.setattr(handlers.bot, "api", vk_api)
    render_block = AsyncMock()
    save_user_field = AsyncMock()
    monkeypatch.setattr(handlers, "render_block", render_block)
    monkeypatch.setattr(handlers, "save_user_field", save_user_field)

    pending = {"save_as": "phone", "next": "consultation_contact", "validate": "phone"}
    state.AWAITING_INPUT[5] = pending
    message = make_message(from_id=5, peer_id=6, text="не номер телефона")

    await handlers._handle_fallback_text(message)

    save_user_field.assert_not_awaited()
    render_block.assert_not_awaited()
    vk_api.messages.send.assert_awaited_once()
    assert "номер телефона" in vk_api.messages.send.call_args.kwargs["message"]
    assert state.AWAITING_INPUT[5] is pending  # ждём ввод повторно


async def test_handle_fallback_text_accepts_valid_phone_and_normalizes_it(vk_api, monkeypatch):
    monkeypatch.setattr(handlers.bot, "api", vk_api)
    render_block = AsyncMock()
    save_user_field = AsyncMock()
    monkeypatch.setattr(handlers, "render_block", render_block)
    monkeypatch.setattr(handlers, "save_user_field", save_user_field)

    state.AWAITING_INPUT[5] = {"save_as": "phone", "next": "consultation_contact", "validate": "phone"}
    message = make_message(from_id=5, peer_id=6, text="8 (999) 123-45-67")

    await handlers._handle_fallback_text(message)

    assert state.USER_DATA[5]["phone"] == "+79991234567"
    save_user_field.assert_awaited_once_with(5, "phone", "+79991234567")
    render_block.assert_awaited_once_with(vk_api, 6, 5, "consultation_contact", replace=False)
    assert 5 not in state.AWAITING_INPUT
