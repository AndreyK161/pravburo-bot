from unittest.mock import AsyncMock

import state
from antispam import AntiSpamMiddleware
from config import ANTISPAM_MAX_EVENTS, ANTISPAM_MUTE_SECONDS


class FakeMessage:
    """Аналог vkbottle Message (message_new) — отправитель в from_id."""

    def __init__(self, from_id=1, peer_id=1):
        self.from_id = from_id
        self.peer_id = peer_id


class FakeMessageEventObj:
    """Аналог MessageEventObject (message_event, нажатие инлайн-кнопки)."""

    def __init__(self, user_id=1, peer_id=1, event_id="ev1"):
        self.user_id = user_id
        self.peer_id = peer_id
        self.event_id = event_id


async def call(middleware, event, vk_api):
    handler = AsyncMock()
    await middleware(handler, event, {"vk_api": vk_api})
    return handler


async def test_lets_normal_traffic_through(vk_api):
    middleware = AntiSpamMiddleware()
    for _ in range(ANTISPAM_MAX_EVENTS):
        handler = await call(middleware, FakeMessage(from_id=1), vk_api)
        handler.assert_awaited_once()
    vk_api.messages.send.assert_not_awaited()


async def test_mutes_after_exceeding_the_limit_and_warns_once(vk_api):
    middleware = AntiSpamMiddleware()
    for _ in range(ANTISPAM_MAX_EVENTS):
        await call(middleware, FakeMessage(from_id=1), vk_api)

    handler = await call(middleware, FakeMessage(from_id=1), vk_api)
    handler.assert_not_awaited()
    vk_api.messages.send.assert_awaited_once()
    assert 1 in state.SPAM_MUTED_UNTIL

    vk_api.messages.send.reset_mock()
    handler = await call(middleware, FakeMessage(from_id=1), vk_api)
    handler.assert_not_awaited()
    vk_api.messages.send.assert_not_awaited()  # не долбим повторным предупреждением


async def test_muting_one_user_does_not_affect_another(vk_api):
    middleware = AntiSpamMiddleware()
    for _ in range(ANTISPAM_MAX_EVENTS + 1):
        await call(middleware, FakeMessage(from_id=1), vk_api)

    handler = await call(middleware, FakeMessage(from_id=2), vk_api)
    handler.assert_awaited_once()


async def test_message_event_flood_counts_toward_the_same_limit_as_messages(vk_api):
    middleware = AntiSpamMiddleware()
    for _ in range(ANTISPAM_MAX_EVENTS):
        await call(middleware, FakeMessageEventObj(user_id=1), vk_api)

    handler = await call(middleware, FakeMessageEventObj(user_id=1), vk_api)

    handler.assert_not_awaited()
    vk_api.messages.send_message_event_answer.assert_awaited_once()  # снимаем "часики" с кнопки


async def test_unmutes_once_the_window_passes(monkeypatch, vk_api):
    middleware = AntiSpamMiddleware()
    now = 1000.0
    monkeypatch.setattr("antispam.time.monotonic", lambda: now)

    for _ in range(ANTISPAM_MAX_EVENTS + 1):
        await call(middleware, FakeMessage(from_id=1), vk_api)
    assert 1 in state.SPAM_MUTED_UNTIL

    now += ANTISPAM_MUTE_SECONDS + 1
    handler = await call(middleware, FakeMessage(from_id=1), vk_api)
    handler.assert_awaited_once()
    assert 1 not in state.SPAM_MUTED_UNTIL
