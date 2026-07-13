"""create users table

Revision ID: f63a808270f9
Revises:
Create Date: 2026-07-06 10:57:38.146110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f63a808270f9'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            username TEXT,
            name TEXT,
            phone TEXT,
            region TEXT,
            source TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users")
