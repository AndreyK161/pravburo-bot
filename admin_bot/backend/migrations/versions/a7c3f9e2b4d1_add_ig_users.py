"""add ig_users table for future Instagram bot

Revision ID: a7c3f9e2b4d1
Revises: e2f5b8a1d6c3
Create Date: 2026-09-17
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a7c3f9e2b4d1'
down_revision: Union[str, None] = 'e2f5b8a1d6c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Instagram-бота ещё нет, но админка (Пользователи/Статистика/routes_users.py
    # PLATFORM_TABLES) уже готова его принять — таблица той же формы, что
    # tg_users/vk_users (LIKE ... INCLUDING ALL копирует колонки/DEFAULT/PK/NOT NULL,
    # но не FK на tags — его добавляем отдельно, как и для vk_users).
    op.execute("CREATE TABLE IF NOT EXISTS ig_users (LIKE tg_users INCLUDING ALL)")
    op.execute(
        "ALTER TABLE ig_users ADD CONSTRAINT ig_users_tag_id_fkey "
        "FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ig_users")
