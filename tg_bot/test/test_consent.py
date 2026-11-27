from types import SimpleNamespace
from unittest.mock import AsyncMock

import database
import handlers
import scenario_engine


async def test_consent_survives_rechecks_and_is_scoped_by_bot_and_version():
    user_id = -9876543210123
    async with database.DB_POOL.acquire() as conn:
        await conn.execute("DELETE FROM bot_consents WHERE user_id = $1", user_id)
    try:
        assert await database.require_bot_consent(user_id, 100, "old", "welcome")
        assert await database.accept_bot_consent(user_id, 100, "old") == "welcome"
        assert await database.require_bot_consent(user_id, 100, "new", "advertising_consultation_checklist")
        assert await database.accept_bot_consent(user_id, 100, "new") == "advertising_consultation_checklist"
        for _ in range(3):
            assert not await database.require_bot_consent(user_id, 100, "new", "welcome")
        assert await database.accept_bot_consent(user_id, 100, "new") is None
        assert await database.require_bot_consent(user_id, 101, "new", "welcome")
    finally:
        async with database.DB_POOL.acquire() as conn:
            await conn.execute("DELETE FROM bot_consents WHERE user_id = $1", user_id)


async def test_gate_keeps_deeplink_destination(monkeypatch):
    require = AsyncMock(return_value=True)
    monkeypatch.setattr(scenario_engine, "require_bot_consent", require)
    bot = SimpleNamespace(id=100)
    assert await scenario_engine.gate_next_block(bot, 7, "advertising_consultation_checklist") == "consent"
    require.assert_awaited_once_with(7, 100, "new_bot_v1", "advertising_consultation_checklist")


async def test_accept_resumes_persisted_destination_once(monkeypatch):
    accept = AsyncMock(side_effect=["advertising_consultation_checklist", None])
    render = AsyncMock()
    monkeypatch.setattr(handlers, "accept_bot_consent", accept)
    monkeypatch.setattr(handlers, "mark_active", AsyncMock())
    monkeypatch.setattr(handlers, "gate_next_block", AsyncMock(return_value="advertising_consultation_checklist"))
    monkeypatch.setattr(handlers, "render_block", render)
    callback = SimpleNamespace(from_user=SimpleNamespace(id=7),
        message=SimpleNamespace(chat=SimpleNamespace(id=8)), answer=AsyncMock())
    bot = SimpleNamespace(id=100)
    await handlers.consent_accept_handler(callback, bot)
    await handlers.consent_accept_handler(callback, bot)
    render.assert_awaited_once_with(bot, 8, 7, "advertising_consultation_checklist", replace=False)
