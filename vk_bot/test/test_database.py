from contextlib import asynccontextmanager

import pytest

import database


class FakeConnection:
    def __init__(self):
        self.calls = []

    async def execute(self, query, *args):
        self.calls.append((query, args))


class FakePool:
    def __init__(self):
        self.conn = FakeConnection()

    @asynccontextmanager
    async def acquire(self):
        yield self.conn


@pytest.fixture
def fake_pool(monkeypatch):
    pool = FakePool()
    monkeypatch.setattr(database, "DB_POOL", pool)
    return pool


async def test_upsert_user_writes_expected_args(fake_pool):
    await database.upsert_user(user_id=1, chat_id=2, username="tester", source="YDX-DIRECT")

    query, args = fake_pool.conn.calls[0]
    assert "INSERT INTO vk_users" in query
    assert args == (1, 2, "tester", "YDX-DIRECT")


async def test_upsert_user_does_not_overwrite_source_on_conflict(fake_pool):
    await database.upsert_user(user_id=1, chat_id=2, username="tester", source="YDX-DIRECT")

    query, _ = fake_pool.conn.calls[0]
    # source сознательно не входит в SET — иначе повторный старт затирал бы метку
    assert "SET chat_id = $2, username = $3, updated_at = now()" in query
    assert "source" not in query.split("SET", 1)[1]


async def test_save_user_field_allowed_column_writes(fake_pool):
    await database.save_user_field(user_id=1, field="phone", value="+79990001122")

    assert len(fake_pool.conn.calls) == 1
    query, args = fake_pool.conn.calls[0]
    assert "UPDATE vk_users SET phone = $1" in query
    assert args == ("+79990001122", 1)


async def test_save_user_field_rejects_unknown_column(fake_pool):
    # Если бы это не проверялось, сюда можно было бы подставить что угодно,
    # например значение save_as из JSON-сценария, как имя колонки в SQL.
    await database.save_user_field(user_id=1, field="user_id = 0; --", value="hacked")

    assert fake_pool.conn.calls == []
