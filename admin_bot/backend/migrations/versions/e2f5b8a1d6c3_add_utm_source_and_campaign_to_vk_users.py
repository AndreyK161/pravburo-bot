"""add utm_source and utm_campaign to vk_users

Revision ID: e2f5b8a1d6c3
Revises: d8a3e6f1c4b9
Create Date: 2026-08-19
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e2f5b8a1d6c3'
down_revision: Union[str, None] = 'd8a3e6f1c4b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # vk_users всегда держали с той же формой колонок, что и tg_users (LIKE ... INCLUDING ALL
    # при создании таблицы), а routes_users.py делает "SELECT *, platform FROM tg_users
    # UNION ALL SELECT *, platform FROM vk_users" — расхождение числа колонок ломает UNION ALL.
    # vk_bot эти поля не заполняет (у него своя механика диплинков), но колонки должны быть.
    op.execute("ALTER TABLE vk_users ADD COLUMN IF NOT EXISTS utm_source TEXT")
    op.execute("ALTER TABLE vk_users ADD COLUMN IF NOT EXISTS utm_campaign TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE vk_users DROP COLUMN IF EXISTS utm_campaign")
    op.execute("ALTER TABLE vk_users DROP COLUMN IF EXISTS utm_source")
