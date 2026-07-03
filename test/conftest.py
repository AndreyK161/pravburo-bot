from unittest.mock import AsyncMock

import pytest

import state


@pytest.fixture(autouse=True)
def reset_state():
    """Обнуляет глобальную "память" бота перед каждым тестом, чтобы тесты не влияли друг на друга."""
    state.USER_ACTIVITY.clear()
    state.LAST_BOT_MESSAGE.clear()
    state.AWAITING_INPUT.clear()
    state.USER_DATA.clear()
    yield
    state.USER_ACTIVITY.clear()
    state.LAST_BOT_MESSAGE.clear()
    state.AWAITING_INPUT.clear()
    state.USER_DATA.clear()


@pytest.fixture
def bot():
    """AsyncMock вместо реального aiogram Bot — любой вызов (send_message и т.п.) просто пишется в mock_calls."""
    return AsyncMock()
