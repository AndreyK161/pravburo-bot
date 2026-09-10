import datetime
from unittest.mock import AsyncMock

from aiogram.types import CallbackQuery, Chat, Message, User

import state
from antispam import AntiSpamMiddleware
from config import ANTISPAM_MAX_EVENTS, ANTISPAM_MUTE_SECONDS


def make_message(user_id=1, chat_id=1, text="hi"):
    return Message(
        message_id=1,
        date=datetime.datetime.now(),
        chat=Chat(id=chat_id, type="private"),
        from_user=User(id=user_id, is_bot=False, first_name="a"),
        text=text,
    )


def make_callback(user_id=1, chat_id=1, data="block:general_menu"):
    return CallbackQuery(
        id="1",
        from_user=User(id=user_id, is_bot=False, first_name="a"),
        chat_instance="1",
        data=data,
        message=make_message(user_id=user_id, chat_id=chat_id),
    )


async def call(middleware, event, bot):
    handler = AsyncMock()
    await middleware(handler, event, {"tg_bot": bot})
    return handler


async def test_lets_normal_traffic_through(bot):
    middleware = AntiSpamMiddleware()
    for _ in range(ANTISPAM_MAX_EVENTS):
        handler = await call(middleware, make_message(user_id=1), bot)
        handler.assert_awaited_once()
    bot.send_message.assert_not_awaited()


async def test_mutes_after_exceeding_the_limit_and_warns_once(bot):
    middleware = AntiSpamMiddleware()
    for _ in range(ANTISPAM_MAX_EVENTS):
        await call(middleware, make_message(user_id=1), bot)

    handler = await call(middleware, make_message(user_id=1), bot)
    handler.assert_not_awaited()
    bot.send_message.assert_awaited_once()
    assert 1 in state.SPAM_MUTED_UNTIL

    bot.send_message.reset_mock()
    handler = await call(middleware, make_message(user_id=1), bot)
    handler.assert_not_awaited()
    bot.send_message.assert_not_awaited()  # не долбим повторным предупреждением


async def test_muting_one_user_does_not_affect_another(bot):
    middleware = AntiSpamMiddleware()
    for _ in range(ANTISPAM_MAX_EVENTS + 1):
        await call(middleware, make_message(user_id=1), bot)

    handler = await call(middleware, make_message(user_id=2), bot)
    handler.assert_awaited_once()


async def test_callback_flood_counts_toward_the_same_limit_as_messages(bot):
    middleware = AntiSpamMiddleware()
    for _ in range(ANTISPAM_MAX_EVENTS):
        await call(middleware, make_callback(user_id=1), bot)

    callback = make_callback(user_id=1).as_(bot)
    handler = await call(middleware, callback, bot)

    handler.assert_not_awaited()
    bot.assert_awaited_once()  # снимаем "часики" с кнопки через AnswerCallbackQuery


async def test_unmutes_once_the_window_passes(monkeypatch, bot):
    middleware = AntiSpamMiddleware()
    now = 1000.0
    monkeypatch.setattr("antispam.time.monotonic", lambda: now)

    for _ in range(ANTISPAM_MAX_EVENTS + 1):
        await call(middleware, make_message(user_id=1), bot)
    assert 1 in state.SPAM_MUTED_UNTIL

    now += ANTISPAM_MUTE_SECONDS + 1
    handler = await call(middleware, make_message(user_id=1), bot)
    handler.assert_awaited_once()
    assert 1 not in state.SPAM_MUTED_UNTIL
