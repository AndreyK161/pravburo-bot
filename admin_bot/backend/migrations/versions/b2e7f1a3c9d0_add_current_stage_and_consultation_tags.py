"""add current_stage to users and consultation status tags

Revision ID: b2e7f1a3c9d0
Revises: 9f1c2d4e5a6b
Create Date: 2026-07-06 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2e7f1a3c9d0'
down_revision: Union[str, None] = '9f1c2d4e5a6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSULTATION_TAGS = ("Консультация: нет", "Консультация: да")


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS current_stage TEXT")
    bind = op.get_bind()
    for name in CONSULTATION_TAGS:
        bind.execute(sa.text("INSERT INTO tags (name) VALUES (:name) ON CONFLICT (name) DO NOTHING"), {"name": name})


def downgrade() -> None:
    bind = op.get_bind()
    for name in CONSULTATION_TAGS:
        bind.execute(sa.text("DELETE FROM tags WHERE name = :name"), {"name": name})
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS current_stage")
