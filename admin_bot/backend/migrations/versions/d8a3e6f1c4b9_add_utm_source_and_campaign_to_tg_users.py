"""add utm_source and utm_campaign to tg_users

Revision ID: d8a3e6f1c4b9
Revises: 4b7032c79718
Create Date: 2026-08-19
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd8a3e6f1c4b9'
down_revision: Union[str, None] = '4b7032c79718'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # source остаётся как есть (сырой ?start=... целиком, для аудита/обратной
    # совместимости со старыми ссылками без разметки). utm_source/utm_campaign —
    # разобранные из ссылок вида start=<блок>_<источник>_<крео> части, только для tg_users
    # (у vk_users своя механика диплинков, не трогаем).
    op.execute("ALTER TABLE tg_users ADD COLUMN IF NOT EXISTS utm_source TEXT")
    op.execute("ALTER TABLE tg_users ADD COLUMN IF NOT EXISTS utm_campaign TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE tg_users DROP COLUMN IF EXISTS utm_campaign")
    op.execute("ALTER TABLE tg_users DROP COLUMN IF EXISTS utm_source")
