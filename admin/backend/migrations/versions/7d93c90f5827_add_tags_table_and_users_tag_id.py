"""add tags table and users tag_id

Revision ID: 7d93c90f5827
Revises: 
Create Date: 2026-07-06 10:50:26.767191

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7d93c90f5827'
down_revision: Union[str, None] = 'f63a808270f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    # users создаётся ботом при старте (app/database.py), а не alembic-ом,
    # поэтому колонку добавляем с IF NOT EXISTS — на случай гонки с первым запуском бота.
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS tag_id INTEGER REFERENCES tags(id) ON DELETE SET NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS tag_id")
    op.drop_table("tags")
