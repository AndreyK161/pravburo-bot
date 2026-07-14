"""rename users to tg_users, add vk_users, broadcast platform flags

Revision ID: 4b7032c79718
Revises: e1a2b3c4d5f6
Create Date: 2026-07-14
"""
from typing import Sequence, Union

from alembic import op


revision: str = '4b7032c79718'
down_revision: Union[str, None] = 'e1a2b3c4d5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users RENAME TO tg_users")
    op.execute("ALTER TABLE tg_users RENAME CONSTRAINT users_pkey TO tg_users_pkey")

    # LIKE ... INCLUDING ALL копирует колонки, DEFAULT'ы, PK и NOT NULL, но не FK на tags.
    op.execute("CREATE TABLE IF NOT EXISTS vk_users (LIKE tg_users INCLUDING ALL)")
    op.execute(
        "ALTER TABLE vk_users ADD CONSTRAINT vk_users_tag_id_fkey "
        "FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE SET NULL"
    )

    op.execute("ALTER TABLE scheduled_broadcasts ADD COLUMN IF NOT EXISTS send_tg BOOLEAN NOT NULL DEFAULT true")
    op.execute("ALTER TABLE scheduled_broadcasts ADD COLUMN IF NOT EXISTS send_vk BOOLEAN NOT NULL DEFAULT false")


def downgrade() -> None:
    op.execute("ALTER TABLE scheduled_broadcasts DROP COLUMN IF EXISTS send_vk")
    op.execute("ALTER TABLE scheduled_broadcasts DROP COLUMN IF EXISTS send_tg")
    op.execute("DROP TABLE IF EXISTS vk_users")
    op.execute("ALTER TABLE tg_users RENAME CONSTRAINT tg_users_pkey TO users_pkey")
    op.execute("ALTER TABLE tg_users RENAME TO users")
