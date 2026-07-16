from unittest.mock import AsyncMock

import pytest

import database
import state


@pytest.fixture(scope="session", autouse=True)
async def _db_pool():
    """Реальный пул к тестовой БД — часть тестов (handlers/scenario_engine)
    пишет в vk_users через настоящие DB-функции, без реального Postgres они падают
    с AttributeError на DB_POOL. Требует запущенный Postgres (DATABASE_URL в .env)."""
    await database.init_db_pool()
    yield
    await database.close_db_pool()


@pytest.fixture(autouse=True)
def reset_state():
    """Обнуляет глобальную "память" бота перед каждым тестом, чтобы тесты не влияли друг на друга."""
    state.USER_ACTIVITY.clear()
    state.LAST_BOT_MESSAGE.clear()
    state.AWAITING_INPUT.clear()
    state.USER_DATA.clear()
    state.SPAM_EVENT_TIMES.clear()
    state.SPAM_MUTED_UNTIL.clear()
    state.LAST_PROCESSED_MESSAGE_ID.clear()
    state.LAST_PROCESSED_EVENT_ID.clear()
    yield
    state.USER_ACTIVITY.clear()
    state.LAST_BOT_MESSAGE.clear()
    state.AWAITING_INPUT.clear()
    state.USER_DATA.clear()
    state.SPAM_EVENT_TIMES.clear()
    state.SPAM_MUTED_UNTIL.clear()
    state.LAST_PROCESSED_MESSAGE_ID.clear()
    state.LAST_PROCESSED_EVENT_ID.clear()


@pytest.fixture
def vk_api():
    """AsyncMock вместо реального vkbottle API — любой вызов (messages.send и т.п.)
    просто пишется в mock_calls."""
    return AsyncMock()
