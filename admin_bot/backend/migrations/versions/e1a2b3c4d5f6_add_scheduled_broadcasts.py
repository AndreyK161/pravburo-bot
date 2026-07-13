"""add scheduled_broadcasts table

Revision ID: e1a2b3c4d5f6
Revises: c7a1d9e3f2b8
Create Date: 2026-07-13
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e1a2b3c4d5f6'
down_revision: Union[str, None] = 'c7a1d9e3f2b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_broadcasts (
            id UUID PRIMARY KEY,
            text TEXT NOT NULL,
            tag_id INTEGER REFERENCES tags(id) ON DELETE SET NULL,
            image_bytes BYTEA,
            image_filename TEXT,
            scheduled_at TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            total INTEGER,
            sent INTEGER NOT NULL DEFAULT 0,
            blocked INTEGER NOT NULL DEFAULT 0,
            failed INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS scheduled_broadcasts")
